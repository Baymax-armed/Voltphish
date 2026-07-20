import { useEffect, useState } from "react";
import { api, ApiError } from "../api";
import type { AiSettings } from "../types";
import { FormSkeleton } from "../components/ui";
import { useToast } from "../components/Toast";

// Suggested models per provider (a "Custom…" option covers anything else).
const MODEL_PRESETS: Record<string, { value: string; label: string }[]> = {
  anthropic: [
    { value: "claude-sonnet-5", label: "Claude Sonnet 5 — balanced (recommended)" },
    { value: "claude-opus-4-8", label: "Claude Opus 4.8 — most capable" },
    { value: "claude-haiku-4-5-20251001", label: "Claude Haiku 4.5 — fastest & cheapest" },
  ],
  openai: [
    { value: "gpt-4o", label: "GPT-4o — balanced (recommended)" },
    { value: "gpt-4o-mini", label: "GPT-4o mini — fast & cheap" },
    { value: "gpt-4.1", label: "GPT-4.1 — capable" },
  ],
  google: [
    { value: "gemini-1.5-flash", label: "Gemini 1.5 Flash — fast & cheap (recommended)" },
    { value: "gemini-1.5-pro", label: "Gemini 1.5 Pro — most capable" },
    { value: "gemini-2.0-flash", label: "Gemini 2.0 Flash — newest" },
  ],
};

const KEY_HELP: Record<string, string> = {
  anthropic: "console.anthropic.com → API Keys (sk-ant-…)",
  openai: "platform.openai.com → API Keys (sk-…)",
  google: "aistudio.google.com → Get API key (AIza…)",
};

export default function Settings() {
  const { notify } = useToast();
  const [cfg, setCfg] = useState<AiSettings | null>(null);
  const [provider, setProvider] = useState("anthropic");
  const [model, setModel] = useState("claude-sonnet-5");
  const [custom, setCustom] = useState(false);
  const [apiKey, setApiKey] = useState("");
  const [busy, setBusy] = useState(false);
  const [testing, setTesting] = useState(false);

  useEffect(() => {
    api
      .getAiSettings()
      .then((s) => {
        setCfg(s);
        setProvider(s.provider);
        setModel(s.model);
        setCustom(!(MODEL_PRESETS[s.provider] || []).some((m) => m.value === s.model));
      })
      .catch(() =>
        setCfg({ provider: "anthropic", model: "claude-sonnet-5", has_key: false, key_hint: "", providers: [] }),
      );
  }, []);

  const changeProvider = (p: string) => {
    setProvider(p);
    const presets = MODEL_PRESETS[p] || [];
    setModel(presets[0]?.value ?? "");
    setCustom(false);
    setApiKey("");
  };

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    const payload: Record<string, unknown> = { provider, model };
    if (apiKey) payload.api_key = apiKey;
    try {
      const s = await api.updateAiSettings(payload);
      setCfg(s);
      setApiKey("");
      notify("AI settings saved.", "ok");
    } catch (err) {
      notify(err instanceof ApiError ? err.message : "Save failed", "error");
    } finally {
      setBusy(false);
    }
  };

  const test = async () => {
    setTesting(true);
    try {
      const r = await api.testAiSettings();
      notify(r.detail, "ok");
    } catch (err) {
      notify(err instanceof ApiError ? err.message : "Test failed", "error");
    } finally {
      setTesting(false);
    }
  };

  const providers =
    cfg?.providers?.length
      ? cfg.providers
      : [
          { value: "anthropic", label: "Anthropic (Claude)" },
          { value: "openai", label: "OpenAI (GPT)" },
          { value: "google", label: "Google (Gemini)" },
        ];
  // Key status only reliable for the currently-saved provider.
  const savedProvider = cfg && provider === cfg.provider;
  const presets = MODEL_PRESETS[provider] || [];

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Settings</h1>
          <div className="page-sub">Configure the AI provider used to generate content</div>
        </div>
      </div>

      {!cfg ? (
        <div className="card" style={{ maxWidth: 640 }}>
          <FormSkeleton fields={3} />
        </div>
      ) : (
        <div className="card" style={{ maxWidth: 640 }}>
          <h2 style={{ margin: "0 0 4px", fontSize: 16 }}>✨ AI generation</h2>
          <p className="hint" style={{ marginBottom: 18 }}>
            Powers the <strong>“Generate with AI”</strong> button in the email template editor. Pick a provider and
            paste that provider's API key — it's encrypted at rest and never shown again.
          </p>

          <form onSubmit={save}>
            <div className="row2">
              <div className="field">
                <label>Provider</label>
                <select value={provider} onChange={(e) => changeProvider(e.target.value)}>
                  {providers.map((p) => (
                    <option key={p.value} value={p.value}>
                      {p.label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="field">
                <label>Model</label>
                <select
                  value={custom ? "__custom" : model}
                  onChange={(e) => {
                    if (e.target.value === "__custom") setCustom(true);
                    else {
                      setCustom(false);
                      setModel(e.target.value);
                    }
                  }}
                >
                  {presets.map((m) => (
                    <option key={m.value} value={m.value}>
                      {m.label}
                    </option>
                  ))}
                  <option value="__custom">Custom model ID…</option>
                </select>
              </div>
            </div>
            {custom && (
              <div className="field">
                <label>Custom model ID</label>
                <input value={model} onChange={(e) => setModel(e.target.value)} placeholder="model-id…" required />
              </div>
            )}

            <div className="field">
              <label>
                API key{" "}
                <span className="hint">
                  {savedProvider && cfg.has_key
                    ? `set (${cfg.key_hint}) — leave blank to keep it`
                    : `enter your ${providers.find((p) => p.value === provider)?.label ?? provider} key`}
                </span>
              </label>
              <input
                type="password"
                value={apiKey}
                autoComplete="new-password"
                placeholder={savedProvider && cfg.has_key ? "••••••••••••  (unchanged)" : "paste API key…"}
                onChange={(e) => setApiKey(e.target.value)}
              />
              <span className="hint" style={{ marginTop: 4 }}>
                Get one at <span className="mono">{KEY_HELP[provider]}</span>
              </span>
            </div>

            <div className="btn-row" style={{ justifyContent: "flex-end", marginTop: 10 }}>
              <button type="button" className="btn" onClick={test} disabled={testing || !(savedProvider && cfg.has_key)}>
                {testing ? "Testing…" : "🔌 Test connection"}
              </button>
              <button className="btn primary" disabled={busy}>
                {busy ? "Saving…" : "Save"}
              </button>
            </div>
          </form>

          <div className="banner" style={{ marginTop: 18, marginBottom: 0 }}>
            💡 Supports <strong>Anthropic (Claude)</strong>, <strong>OpenAI (GPT)</strong>, and{" "}
            <strong>Google (Gemini)</strong>. Each provider's key is stored separately, so you can switch anytime.
            Without a key, “Generate with AI” shows a friendly "not configured" message.
          </div>
        </div>
      )}
    </>
  );
}
