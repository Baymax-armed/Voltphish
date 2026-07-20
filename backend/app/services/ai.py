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

log = logging.getLogger("phishsim.ai")

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


async def generate_template(scenario: str, difficulty: str = "medium") -> dict:
    settings = get_settings()
    if not settings.ai_api_key:
        raise AiError(
            "AI generation is not configured. Set PHISHSIM_AI_API_KEY (an "
            "Anthropic API key) to enable it."
        )

    hint = _DIFFICULTY_HINT.get(difficulty, _DIFFICULTY_HINT["medium"])
    user_msg = (
        f"Write a simulated phishing training email for this scenario:\n\n{scenario}\n\n"
        f"Difficulty: {difficulty}. {hint}"
    )

    payload = {
        "model": settings.ai_model,
        "max_tokens": 2000,
        "system": _SYSTEM,
        "messages": [{"role": "user", "content": user_msg}],
    }
    headers = {
        "x-api-key": settings.ai_api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(
                f"{settings.ai_base_url.rstrip('/')}/v1/messages",
                headers=headers,
                json=payload,
            )
    except httpx.HTTPError:
        log.exception("AI request failed (network)")
        raise AiError("Could not reach the AI service. Try again shortly.")

    if resp.status_code == 401:
        raise AiError("The configured AI API key was rejected (401). Check PHISHSIM_AI_API_KEY.")
    if resp.status_code == 429:
        raise AiError("The AI service is rate-limited right now. Try again in a moment.")
    if resp.status_code >= 400:
        log.warning("AI request non-2xx: %s", resp.status_code)
        raise AiError("The AI service returned an error. Try a different prompt.")

    try:
        data = resp.json()
        text = "".join(
            block.get("text", "") for block in data.get("content", []) if block.get("type") == "text"
        ).strip()
        parsed = _extract_json(text)
    except (ValueError, KeyError, TypeError):
        log.warning("AI response could not be parsed")
        raise AiError("The AI returned an unexpected format. Try again.")

    subject = str(parsed.get("subject", "")).strip()
    html = str(parsed.get("html", "")).strip()
    text_body = str(parsed.get("text", "")).strip()
    name = str(parsed.get("name", "AI template")).strip()[:120]
    if not subject or not (html or text_body):
        raise AiError("The AI did not return a usable email. Try rephrasing the scenario.")

    return {"name": name, "subject": subject[:500], "html": html, "text": text_body}


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
