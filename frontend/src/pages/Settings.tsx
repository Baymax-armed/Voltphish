import { useEffect, useState } from "react";
import { api, ApiError } from "../api";
import type { AiSettings, AllowlistResult, BenchmarkSettings, ImapSettings, SsoSettings, TotpSetup } from "../types";
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
          <div className="page-sub">AI generation, reported-phish mailbox, SSO, benchmarks, allowlists &amp; 2FA</div>
        </div>
      </div>

      <div className="settings-grid">
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

      <ImapCard />
      <SsoCard />
      <BenchmarkCard />
      <AllowlistCard />
      <TwoFactorCard />
      </div>
    </>
  );
}

function AllowlistCard() {
  const { notify } = useToast();
  const [domains, setDomains] = useState("");
  const [ips, setIps] = useState("");
  const [urls, setUrls] = useState("");
  const [result, setResult] = useState<AllowlistResult | null>(null);
  const [busy, setBusy] = useState(false);

  const split = (s: string) => s.split(/[\s,;]+/).map((x) => x.trim()).filter(Boolean);

  const generate = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      setResult(await api.generateAllowlist({ domains: split(domains), ips: split(ips), urls: split(urls) }));
    } catch (err) {
      notify(err instanceof ApiError ? err.message : "Failed", "error");
    } finally {
      setBusy(false);
    }
  };

  const copy = (s: AllowlistResult["sections"][number]) => {
    const text = `${s.platform}\n${s.where}\n\n${s.entries.join("\n")}\n\nSteps:\n${s.steps.map((x, i) => `${i + 1}. ${x}`).join("\n")}${s.warning ? `\n\n⚠ ${s.warning}` : ""}`;
    navigator.clipboard?.writeText(text).then(() => notify("Copied.", "ok"), () => {});
  };

  return (
    <div className="card" style={{ maxWidth: 640, marginTop: 20 }}>
      <h2 style={{ margin: "0 0 4px", fontSize: 16 }}>📬 Deliverability allowlist generator</h2>
      <p className="hint" style={{ marginBottom: 18 }}>
        Generate the exact, scoped allowlist entries to get simulation mail past your org's filters without weakening
        real security. Enter your sending domains, IPs, and tracking URLs.
      </p>
      <form onSubmit={generate}>
        <div className="field">
          <label>Sending domains</label>
          <input value={domains} onChange={(e) => setDomains(e.target.value)} placeholder="phish-sim.com, mail.corp-training.com" />
        </div>
        <div className="row2">
          <div className="field">
            <label>Sending IPs</label>
            <input value={ips} onChange={(e) => setIps(e.target.value)} placeholder="203.0.113.10, 203.0.113.11" />
          </div>
          <div className="field">
            <label>Tracking URLs / hosts</label>
            <input value={urls} onChange={(e) => setUrls(e.target.value)} placeholder="https://track.phish-sim.com" />
          </div>
        </div>
        <div className="btn-row" style={{ justifyContent: "flex-end" }}>
          <button className="btn primary" disabled={busy}>{busy ? "Generating…" : "Generate allowlist"}</button>
        </div>
      </form>

      {result && (
        <div style={{ marginTop: 16, display: "flex", flexDirection: "column", gap: 12 }}>
          {result.sections.map((s) => (
            <div key={s.platform} style={{ border: "1px solid var(--border, #e2e8f0)", borderRadius: 10, padding: 14 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <strong>{s.platform}</strong>
                <button type="button" className="btn" onClick={() => copy(s)}>Copy</button>
              </div>
              <div className="hint" style={{ margin: "4px 0 8px" }}>{s.where}</div>
              {s.entries.map((en, i) => (
                <div key={i} className="mono" style={{ fontSize: 12, marginBottom: 3 }}>{en}</div>
              ))}
              <ol style={{ margin: "10px 0 0", paddingLeft: 18, fontSize: 13, color: "var(--text-dim)" }}>
                {s.steps.map((st, i) => <li key={i} style={{ marginBottom: 3 }}>{st}</li>)}
              </ol>
              {s.warning && (
                <div className="banner" style={{ marginTop: 10, marginBottom: 0, borderColor: "#f59e0b" }}>⚠ {s.warning}</div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function BenchmarkCard() {
  const { notify } = useToast();
  const [f, setF] = useState<BenchmarkSettings | null>(null);
  const [busy, setBusy] = useState(false);
  const set = (k: string, v: unknown) => setF((p) => (p ? { ...p, [k]: v } : p));

  useEffect(() => {
    api.getBenchmarkSettings().then(setF).catch(() => setF(null));
  }, []);

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!f) return;
    setBusy(true);
    try {
      setF(await api.updateBenchmarkSettings({ ...f }));
      notify("Benchmark saved.", "ok");
    } catch (err) {
      notify(err instanceof ApiError ? err.message : "Save failed", "error");
    } finally {
      setBusy(false);
    }
  };

  if (!f) return null;
  return (
    <div className="card" style={{ maxWidth: 640, marginTop: 20 }}>
      <h2 style={{ margin: "0 0 4px", fontSize: 16 }}>📊 Industry benchmark</h2>
      <p className="hint" style={{ marginBottom: 18 }}>
        Show your click &amp; report rates against an industry baseline on the dashboard. A self-hosted tool has no
        cross-customer dataset, so you set the baseline yourself from a public source (Verizon DBIR, a vendor report).
        Nothing is fabricated.
      </p>
      <form onSubmit={save}>
        <div className="field check">
          <input id="bm-en" type="checkbox" checked={f.enabled} onChange={(e) => set("enabled", e.target.checked)} />
          <label htmlFor="bm-en">Show benchmark on dashboard</label>
        </div>
        <div className="field">
          <label>Baseline label</label>
          <input value={f.industry} onChange={(e) => set("industry", e.target.value)} placeholder="Finance industry avg (DBIR 2025)" />
        </div>
        <div className="row2">
          <div className="field">
            <label>Baseline click rate (%)</label>
            <input type="number" step="0.1" min="0" max="100" value={f.baseline_click_rate}
              onChange={(e) => set("baseline_click_rate", Number(e.target.value))} />
          </div>
          <div className="field">
            <label>Baseline report rate (%)</label>
            <input type="number" step="0.1" min="0" max="100" value={f.baseline_report_rate}
              onChange={(e) => set("baseline_report_rate", Number(e.target.value))} />
          </div>
        </div>
        <div className="btn-row" style={{ justifyContent: "flex-end", marginTop: 6 }}>
          <button className="btn primary" disabled={busy}>{busy ? "Saving…" : "Save"}</button>
        </div>
      </form>
    </div>
  );
}

function SsoCard() {
  const { notify } = useToast();
  const [cfg, setCfg] = useState<SsoSettings | null>(null);
  const [f, setF] = useState<SsoSettings & { client_secret: string }>({
    enabled: false, issuer: "", client_id: "", allowed_domains: "", auto_provision: false,
    button_label: "Sign in with SSO", has_secret: false, redirect_uri: "", client_secret: "",
  });
  const [busy, setBusy] = useState(false);
  const set = (k: string, v: unknown) => setF((p) => ({ ...p, [k]: v }));

  useEffect(() => {
    api.getSsoSettings().then((s) => { setCfg(s); setF({ ...s, client_secret: "" }); }).catch(() => setCfg(null));
  }, []);

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    const payload: Record<string, unknown> = {
      enabled: f.enabled, issuer: f.issuer, client_id: f.client_id,
      allowed_domains: f.allowed_domains, auto_provision: f.auto_provision, button_label: f.button_label,
    };
    if (f.client_secret) payload.client_secret = f.client_secret;
    try {
      const s = await api.updateSsoSettings(payload);
      setCfg(s);
      setF({ ...s, client_secret: "" });
      notify("SSO settings saved.", "ok");
    } catch (err) {
      notify(err instanceof ApiError ? err.message : "Save failed", "error");
    } finally {
      setBusy(false);
    }
  };

  if (!cfg) return null;
  const copy = (t: string) => navigator.clipboard?.writeText(t).then(() => notify("Copied.", "ok"), () => {});

  return (
    <div className="card" style={{ maxWidth: 640, marginTop: 20 }}>
      <h2 style={{ margin: "0 0 4px", fontSize: 16 }}>🔐 Single Sign-On (OIDC)</h2>
      <p className="hint" style={{ marginBottom: 18 }}>
        Let admins sign in with your identity provider (Okta, Microsoft Entra ID, Google, Auth0, Keycloak). Uses
        OpenID Connect with PKCE; the client secret is encrypted at rest.
      </p>
      <form onSubmit={save}>
        <div className="field check">
          <input id="sso-en" type="checkbox" checked={f.enabled} onChange={(e) => set("enabled", e.target.checked)} />
          <label htmlFor="sso-en">Enable SSO sign-in</label>
        </div>
        <div className="field">
          <label>Issuer URL <span className="hint">(discovery base)</span></label>
          <input value={f.issuer} onChange={(e) => set("issuer", e.target.value)}
            placeholder="https://your-org.okta.com" />
        </div>
        <div className="row2">
          <div className="field">
            <label>Client ID</label>
            <input value={f.client_id} onChange={(e) => set("client_id", e.target.value)} />
          </div>
          <div className="field">
            <label>Client secret <span className="hint">{cfg.has_secret ? "set — blank keeps it" : "not set"}</span></label>
            <input type="password" value={f.client_secret} autoComplete="new-password"
              placeholder={cfg.has_secret ? "•••••••• (unchanged)" : "paste secret"}
              onChange={(e) => set("client_secret", e.target.value)} />
          </div>
        </div>
        <div className="row2">
          <div className="field">
            <label>Allowed email domains <span className="hint">(comma-sep, blank = any)</span></label>
            <input value={f.allowed_domains} onChange={(e) => set("allowed_domains", e.target.value)} placeholder="corp.com" />
          </div>
          <div className="field">
            <label>Button label</label>
            <input value={f.button_label} onChange={(e) => set("button_label", e.target.value)} />
          </div>
        </div>
        <div className="field check">
          <input id="sso-prov" type="checkbox" checked={f.auto_provision} onChange={(e) => set("auto_provision", e.target.checked)} />
          <label htmlFor="sso-prov">Auto-create accounts on first SSO login (as operator)</label>
        </div>
        <div className="field">
          <label>Redirect URI <span className="hint">— register this in your IdP</span></label>
          <div style={{ display: "flex", gap: 6 }}>
            <input readOnly value={cfg.redirect_uri} className="mono" style={{ flex: 1 }} />
            <button type="button" className="btn" onClick={() => copy(cfg.redirect_uri)}>Copy</button>
          </div>
        </div>
        <div className="btn-row" style={{ justifyContent: "flex-end", marginTop: 10 }}>
          <button className="btn primary" disabled={busy}>{busy ? "Saving…" : "Save"}</button>
        </div>
      </form>
      <div className="banner" style={{ marginTop: 18, marginBottom: 0 }}>
        💡 In your IdP, create an <strong>OIDC web app</strong>, add the redirect URI above, and scope{" "}
        <span className="mono">openid email profile</span>. Password login still works alongside SSO.
      </div>
    </div>
  );
}

function TwoFactorCard() {
  const { notify } = useToast();
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [setup, setSetup] = useState<TotpSetup | null>(null);
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [showKey, setShowKey] = useState(false);

  useEffect(() => {
    api.totpStatus().then((s) => setEnabled(s.enabled)).catch(() => setEnabled(false));
  }, []);

  const beginSetup = async () => {
    setBusy(true);
    try {
      setSetup(await api.totpSetup());
      setCode("");
    } catch (err) {
      notify(err instanceof ApiError ? err.message : "Couldn't start setup", "error");
    } finally {
      setBusy(false);
    }
  };

  const confirmEnable = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      await api.totpEnable(code);
      setEnabled(true);
      setSetup(null);
      setCode("");
      notify("Two-factor authentication is on.", "ok");
    } catch (err) {
      notify(err instanceof ApiError ? err.message : "Invalid code", "error");
    } finally {
      setBusy(false);
    }
  };

  const disable = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      await api.totpDisable(code);
      setEnabled(false);
      setCode("");
      notify("Two-factor authentication is off.", "ok");
    } catch (err) {
      notify(err instanceof ApiError ? err.message : "Invalid code", "error");
    } finally {
      setBusy(false);
    }
  };

  if (enabled === null) return null;

  return (
    <div className="card" style={{ maxWidth: 640, marginTop: 20 }}>
      <h2 style={{ margin: "0 0 4px", fontSize: 16 }}>
        🔐 Two-factor authentication
        <span
          className="pill"
          style={{
            marginLeft: 10,
            background: enabled ? "var(--ok-bg, #dcfce7)" : "var(--muted-bg, #f1f5f9)",
            color: enabled ? "var(--ok, #166534)" : "var(--muted, #64748b)",
          }}
        >
          {enabled ? "On" : "Off"}
        </span>
      </h2>
      <p className="hint" style={{ marginBottom: 18 }}>
        Protect your admin account with a time-based code from an authenticator app (Google Authenticator, Microsoft
        Authenticator, Authy, 1Password). After your password, you'll be asked for a 6-digit code.
      </p>

      {enabled ? (
        <form onSubmit={disable}>
          <div className="field">
            <label>Enter a current code to turn it off</label>
            <input
              type="text"
              inputMode="numeric"
              maxLength={6}
              placeholder="123456"
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
              required
            />
          </div>
          <div className="btn-row" style={{ justifyContent: "flex-end" }}>
            <button className="btn danger-solid" disabled={busy || code.length !== 6}>
              {busy ? "Working…" : "Turn off 2FA"}
            </button>
          </div>
        </form>
      ) : setup ? (
        <form onSubmit={confirmEnable}>
          <p className="hint" style={{ marginBottom: 12 }}>
            <strong>1.</strong> Scan this QR code with your authenticator app:
          </p>
          <div style={{ textAlign: "center", marginBottom: 12 }}>
            <img
              src={setup.qr_data_uri}
              alt="2FA QR code"
              width={180}
              height={180}
              style={{ borderRadius: 8, border: "1px solid var(--border, #e2e8f0)" }}
            />
          </div>
          <p className="hint" style={{ marginBottom: 6 }}>
            Can't scan?{" "}
            <button
              type="button"
              className="linklike"
              onClick={() => setShowKey((s) => !s)}
              style={{ background: "none", border: "none", color: "var(--accent)", cursor: "pointer", padding: 0 }}
            >
              {showKey ? "hide" : "enter the key manually"}
            </button>
          </p>
          {showKey && (
            <div className="mono" style={{ wordBreak: "break-all", marginBottom: 12, fontSize: 13 }}>
              {setup.secret}
            </div>
          )}
          <div className="field">
            <label>
              <strong>2.</strong> Enter the 6-digit code it shows
            </label>
            <input
              type="text"
              inputMode="numeric"
              maxLength={6}
              autoFocus
              placeholder="123456"
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
              required
            />
          </div>
          <div className="btn-row" style={{ justifyContent: "flex-end" }}>
            <button type="button" className="btn" onClick={() => setSetup(null)} disabled={busy}>
              Cancel
            </button>
            <button className="btn primary" disabled={busy || code.length !== 6}>
              {busy ? "Verifying…" : "Verify & enable"}
            </button>
          </div>
        </form>
      ) : (
        <div className="btn-row" style={{ justifyContent: "flex-start" }}>
          <button className="btn primary" onClick={beginSetup} disabled={busy}>
            {busy ? "Starting…" : "Set up 2FA"}
          </button>
        </div>
      )}
    </div>
  );
}

function ImapCard() {
  const { notify } = useToast();
  const [cfg, setCfg] = useState<ImapSettings | null>(null);
  const [f, setF] = useState<ImapSettings & { password: string }>({
    enabled: false, host: "", port: 993, username: "", ssl: true, folder: "INBOX", has_password: false, password: "",
  });
  const [busy, setBusy] = useState(false);
  const [testing, setTesting] = useState(false);
  const set = (k: string, v: unknown) => setF((p) => ({ ...p, [k]: v }));

  useEffect(() => {
    api
      .getImapSettings()
      .then((s) => {
        setCfg(s);
        setF({ ...s, password: "" });
      })
      .catch(() => setCfg(null));
  }, []);

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    const payload: Record<string, unknown> = {
      enabled: f.enabled, host: f.host, port: f.port, username: f.username, ssl: f.ssl, folder: f.folder,
    };
    if (f.password) payload.password = f.password;
    try {
      const s = await api.updateImapSettings(payload);
      setCfg(s);
      setF({ ...s, password: "" });
      notify("Mailbox settings saved.", "ok");
    } catch (err) {
      notify(err instanceof ApiError ? err.message : "Save failed", "error");
    } finally {
      setBusy(false);
    }
  };

  const test = async () => {
    setTesting(true);
    try {
      const r = await api.testImapSettings();
      notify(r.detail, "ok");
    } catch (err) {
      notify(err instanceof ApiError ? err.message : "Test failed", "error");
    } finally {
      setTesting(false);
    }
  };

  if (!cfg) return null;

  return (
    <div className="card" style={{ maxWidth: 640, marginTop: 20 }}>
      <h2 style={{ margin: "0 0 4px", fontSize: 16 }}>📥 Reported-phish mailbox (IMAP)</h2>
      <p className="hint" style={{ marginBottom: 18 }}>
        Employees report a simulated phish by <strong>forwarding it to a shared mailbox</strong> (e.g.
        <span className="mono"> phish-report@company.com</span>). VoltPhish polls it every ~60s, matches the report to
        the recipient, and credits them as a <strong>Security Champion</strong>.
      </p>
      <form onSubmit={save}>
        <div className="field check">
          <input id="imap-en" type="checkbox" checked={f.enabled} onChange={(e) => set("enabled", e.target.checked)} />
          <label htmlFor="imap-en">Enable monitoring</label>
        </div>
        <div className="row2">
          <div className="field">
            <label>IMAP host</label>
            <input value={f.host} onChange={(e) => set("host", e.target.value)} placeholder="imap.gmail.com" />
          </div>
          <div className="field">
            <label>Port</label>
            <input type="number" value={f.port} onChange={(e) => set("port", Number(e.target.value))} />
          </div>
        </div>
        <div className="row2">
          <div className="field">
            <label>Username</label>
            <input value={f.username} onChange={(e) => set("username", e.target.value)} placeholder="phish-report@company.com" />
          </div>
          <div className="field">
            <label>
              Password{" "}
              <span className="hint">{cfg.has_password ? "set — leave blank to keep" : "not set"}</span>
            </label>
            <input
              type="password"
              value={f.password}
              autoComplete="new-password"
              placeholder={cfg.has_password ? "•••••••• (unchanged)" : "app password"}
              onChange={(e) => set("password", e.target.value)}
            />
          </div>
        </div>
        <div className="row2">
          <div className="field">
            <label>Folder</label>
            <input value={f.folder} onChange={(e) => set("folder", e.target.value)} placeholder="INBOX" />
          </div>
          <div className="field check" style={{ alignItems: "flex-end", paddingBottom: 10 }}>
            <input id="imap-ssl" type="checkbox" checked={f.ssl} onChange={(e) => set("ssl", e.target.checked)} />
            <label htmlFor="imap-ssl">Use SSL/TLS (port 993)</label>
          </div>
        </div>
        <div className="btn-row" style={{ justifyContent: "flex-end", marginTop: 6 }}>
          <button type="button" className="btn" onClick={test} disabled={testing || !cfg.host}>
            {testing ? "Testing…" : "🔌 Test connection"}
          </button>
          <button className="btn primary" disabled={busy}>
            {busy ? "Saving…" : "Save"}
          </button>
        </div>
      </form>
      <div className="banner" style={{ marginTop: 18, marginBottom: 0 }}>
        💡 For Gmail/Google Workspace use an <strong>App Password</strong> (not your login password) and host{" "}
        <span className="mono">imap.gmail.com</span>. Reports match by the tracking link inside the forwarded email, or
        by the reporter's own address.
      </div>
    </div>
  );
}
