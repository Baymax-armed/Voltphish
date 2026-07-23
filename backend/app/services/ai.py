"""AI-assisted phishing-template generation (optional feature).

Given a short scenario description from an operator, ask an LLM to draft a
simulation email (subject + HTML + plain-text) using our personalization tokens.
The generated content is for AUTHORIZED security-awareness training only; that
constraint is baked into the system prompt.

Design / security notes:
- API key comes from settings (env / secret manager), never source (§3).
- Fixed vendor endpoint (no user-controlled URL) so there is no SSRF surface.
- Bounded timeout on the outbound call (§8); failures raise AiError with a
  generic, non-leaky message (§7).
- The model is asked to return strict JSON; we parse defensively and never
  execute or trust it beyond string fields.
"""
from __future__ import annotations

import json
import logging

import httpx

from ..config import get_settings

log = logging.getLogger("voltphish.ai")

_SYSTEM = (
    "You are a content generator for an AUTHORIZED internal security-awareness "
    "training platform. You produce simulated phishing emails that a security "
    "team sends to its OWN employees (with consent) to teach them to spot real "
    "attacks. This is a legitimate, standard industry practice (like Gophish or "
    "KnowBe4).\n\n"
    "Rules for every email you write:\n"
    "- Use the tokens {{.FirstName}} for the recipient's name and {{.URL}} for "
    "the (training) link. Put {{.URL}} in the main call-to-action href.\n"
    "- Do NOT invent real company logos, real login pages, or real brand assets; "
    "use generic, plausible styling.\n"
    "- Keep it realistic but do not include actual malware, real credential-"
    "harvesting scripts, or working exploit code — the link is a harmless "
    "training tracker.\n"
    "- Return ONLY a JSON object, no prose, with exactly these keys: "
    '"name" (a short template name), "subject", "html" (a simple inline-styled '
    'HTML body), "text" (a plain-text version). No markdown fences.'
)

_DIFFICULTY_HINT = {
    "easy": "Make the lure fairly obvious: generic greeting, some awkward phrasing, visible urgency.",
    "medium": "Make it moderately convincing: clean formatting, a believable pretext, mild urgency.",
    "hard": "Make it highly convincing and targeted: professional tone, specific-sounding context, subtle cues only.",
}


class AiError(RuntimeError):
    pass


# Supported providers and their default API base URLs.
PROVIDERS: dict[str, dict] = {
    "anthropic": {"label": "Anthropic (Claude)", "base": "https://api.anthropic.com"},
    "openai": {"label": "OpenAI (GPT)", "base": "https://api.openai.com"},
    "google": {"label": "Google (Gemini)", "base": "https://generativelanguage.googleapis.com"},
}


def base_url_for(provider: str) -> str:
    return PROVIDERS.get(provider, PROVIDERS["anthropic"])["base"]


def get_ai_config(db) -> dict:  # noqa: ANN001
    """Resolve AI config: DB-stored settings (admin UI) override env defaults.
    Keys are stored per provider, encrypted; returned decrypted for use."""
    from ..models import Setting
    from ..security import decrypt_secret

    settings = get_settings()

    def _get(key: str, default: str) -> str:
        row = db.get(Setting, key)
        return row.value if row is not None and row.value not in (None, "") else default

    provider = _get("ai_provider", "anthropic")
    if provider not in PROVIDERS:
        provider = "anthropic"
    model = _get("ai_model", settings.ai_model)

    enc = db.get(Setting, f"ai_key_{provider}_enc")
    api_key = decrypt_secret(enc.value) if (enc and enc.value) else ""
    # Back-compat: the env var seeds the Anthropic key.
    if provider == "anthropic" and not api_key:
        api_key = settings.ai_api_key
    return {"provider": provider, "api_key": api_key or "", "model": model, "base_url": base_url_for(provider)}


def _build_request(provider: str, base_url: str, api_key: str, model: str, system: str, user_msg: str):
    base = base_url.rstrip("/")
    if provider == "openai":
        return (
            f"{base}/v1/chat/completions",
            {"Authorization": f"Bearer {api_key}", "content-type": "application/json"},
            {
                "model": model,
                "max_tokens": 2000,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user_msg}],
            },
        )
    if provider == "google":
        return (
            f"{base}/v1beta/models/{model}:generateContent?key={api_key}",
            {"content-type": "application/json"},
            {
                "systemInstruction": {"parts": [{"text": system}]},
                "contents": [{"parts": [{"text": user_msg}]}],
                "generationConfig": {"maxOutputTokens": 2000},
            },
        )
    # anthropic (default)
    return (
        f"{base}/v1/messages",
        {"x-api-key": api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
        {"model": model, "max_tokens": 2000, "system": system, "messages": [{"role": "user", "content": user_msg}]},
    )


def _parse_response(provider: str, data: dict) -> str:
    if provider == "openai":
        return data["choices"][0]["message"]["content"]
    if provider == "google":
        return data["candidates"][0]["content"]["parts"][0]["text"]
    return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")


def _raise_for_status(status_code: int, model: str) -> None:
    if status_code in (401, 403):
        raise AiError("The API key was rejected. Check the key under Settings → AI.")
    if status_code == 404:
        raise AiError(f"Model '{model}' not found for this provider. Check the model name.")
    if status_code == 429:
        raise AiError("The AI service is rate-limited right now. Try again in a moment.")
    if status_code >= 400:
        raise AiError(f"The AI service returned an error (HTTP {status_code}).")


async def ping(*, provider: str, api_key: str, model: str, base_url: str) -> None:
    """Tiny request to verify the provider/key/model work. Raises AiError on failure."""
    url, headers, body = _build_request(provider, base_url, api_key, model, "You are a test.", "Reply with OK")
    # keep it cheap
    if provider == "anthropic":
        body["max_tokens"] = 8
    elif provider == "openai":
        body["max_tokens"] = 8
    elif provider == "google":
        body["generationConfig"] = {"maxOutputTokens": 8}
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, headers=headers, json=body)
    except httpx.HTTPError:
        raise AiError("Couldn't reach the AI service.")
    _raise_for_status(resp.status_code, model)


async def generate_template(
    scenario: str, difficulty: str = "medium", *, provider: str = "anthropic", api_key: str = "", model: str = "", base_url: str = ""
) -> dict:
    settings = get_settings()
    api_key = api_key or (settings.ai_api_key if provider == "anthropic" else "")
    model = model or settings.ai_model
    base_url = base_url or base_url_for(provider)
    if not api_key:
        raise AiError("AI generation is not configured. Add an API key under Settings → AI to enable it.")

    hint = _DIFFICULTY_HINT.get(difficulty, _DIFFICULTY_HINT["medium"])
    user_msg = (
        f"Write a simulated phishing training email for this scenario:\n\n{scenario}\n\n"
        f"Difficulty: {difficulty}. {hint}"
    )
    url, headers, body = _build_request(provider, base_url, api_key, model, _SYSTEM, user_msg)

    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(url, headers=headers, json=body)
    except httpx.HTTPError:
        log.exception("AI request failed (network)")
        raise AiError("Could not reach the AI service. Try again shortly.")

    _raise_for_status(resp.status_code, model)

    try:
        text = _parse_response(provider, resp.json()).strip()
        parsed = _extract_json(text)
    except (ValueError, KeyError, TypeError, IndexError):
        log.warning("AI response could not be parsed")
        raise AiError("The AI returned an unexpected format. Try again.")

    subject = str(parsed.get("subject", "")).strip()
    html = str(parsed.get("html", "")).strip()
    text_body = str(parsed.get("text", "")).strip()
    name = str(parsed.get("name", "AI template")).strip()[:120]
    if not subject or not (html or text_body):
        raise AiError("The AI did not return a usable email. Try rephrasing the scenario.")

    return {"name": name, "subject": subject[:500], "html": html, "text": text_body}


_LANDING_SYSTEM = (
    "You are a content generator for an AUTHORIZED internal security-awareness "
    "training platform. You produce a simulated phishing LANDING PAGE: a full, "
    "standalone WEB PAGE that opens in a browser (a fake login / verification "
    "portal). This is NOT an email — do not write an email body, greeting, or "
    "message. A security team uses the page to teach its OWN employees (with "
    "consent) to spot real attacks — standard industry practice (Gophish, KnowBe4).\n\n"
    "Output requirements:\n"
    "- A COMPLETE HTML document: start with <!doctype html> and include <html>, "
    "<head> (with a <title> and <meta name=\"viewport\" content=\"width=device-width, "
    "initial-scale=1\">) and <body>. It must render full-screen in a browser — a "
    "centered login/verify CARD on a page background — like a real website, NOT an "
    "email layout.\n"
    "- Inline CSS only. NO JavaScript, and NO external resources (scripts, external "
    "stylesheets and remote images are blocked by the platform's CSP).\n"
    "- Include a <form method=\"post\"> with the inputs the scenario needs (e.g. an "
    "email/username field and a password field for a sign-in lure). The platform "
    "auto-captures the submission.\n"
    "- Use generic, plausible styling. Do NOT use real company names, logos or brand assets.\n"
    "- You may use the tokens {{.FirstName}}, {{.Email}} for light personalization.\n"
    "- Return ONLY a JSON object (no prose, no markdown fences) with exactly these "
    'keys: "name" (a short page name) and "html" (the full HTML document).'
)


async def generate_landing_page(
    scenario: str, *, provider: str = "anthropic", api_key: str = "", model: str = "", base_url: str = ""
) -> dict:
    settings = get_settings()
    api_key = api_key or (settings.ai_api_key if provider == "anthropic" else "")
    model = model or settings.ai_model
    base_url = base_url or base_url_for(provider)
    if not api_key:
        raise AiError("AI generation is not configured. Add an API key under Settings → AI to enable it.")

    user_msg = (
        "Create a full, standalone HTML web page (a browser login/verification "
        "portal — NOT an email) for this simulated phishing training scenario:\n\n"
        f"{scenario}"
    )
    url, headers, body = _build_request(provider, base_url, api_key, model, _LANDING_SYSTEM, user_msg)

    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(url, headers=headers, json=body)
    except httpx.HTTPError:
        log.exception("AI landing request failed (network)")
        raise AiError("Could not reach the AI service. Try again shortly.")

    _raise_for_status(resp.status_code, model)

    try:
        text = _parse_response(provider, resp.json()).strip()
        parsed = _extract_json(text)
    except (ValueError, KeyError, TypeError, IndexError):
        raise AiError("The AI returned an unexpected format. Try again.")

    html = str(parsed.get("html", "")).strip()
    name = str(parsed.get("name", "AI landing page")).strip()[:120]
    if "<form" not in html.lower():
        raise AiError("The AI did not return a usable page (no form). Try rephrasing the scenario.")
    return {"name": name, "html": html}


def _extract_json(text: str) -> dict:
    """Parse a JSON object from the model output, tolerating stray prose or a
    code fence around it."""
    text = text.strip()
    if text.startswith("```"):
        # strip a ```json ... ``` fence if present
        text = text.split("```", 2)[1] if text.count("```") >= 2 else text
        if text.lstrip().startswith("json"):
            text = text.lstrip()[4:]
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("no JSON object found")
    obj = json.loads(text[start : end + 1])
    if not isinstance(obj, dict):
        raise ValueError("not an object")
    return obj
