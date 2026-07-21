import { useEffect, useState } from "react";
import { useAuth } from "../auth";
import { api, ApiError } from "../api";

const SSO_ERRORS: Record<string, string> = {
  config: "SSO isn't configured correctly. Contact your administrator.",
  denied: "SSO sign-in was cancelled or denied.",
  verify: "Couldn't verify your SSO sign-in. Please try again.",
  noaccount: "No account exists for your SSO email, and auto-provisioning is off.",
  disabled: "Your account is disabled.",
};

export default function Login() {
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [twoFactor, setTwoFactor] = useState(false);
  const [show, setShow] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [sso, setSso] = useState<{ enabled: boolean; button_label: string } | null>(null);

  useEffect(() => {
    api.ssoInfo().then(setSso).catch(() => setSso(null));
    const params = new URLSearchParams(window.location.search);
    const e = params.get("sso_error");
    if (e) setErr(SSO_ERRORS[e] || "SSO sign-in failed.");
  }, []);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErr(null);
    setBusy(true);
    try {
      const r = await login(email, password, twoFactor ? code : undefined);
      if (r.twoFactorRequired) setTwoFactor(true);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Couldn't sign in. Check your email and password.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="login-wrap ocean">
      <div className="login-card">
        <div className="login-side">
          <img className="brand-img login-logo-img" src="/logo.png" alt="VoltPhish" />
          <div className="login-side-tag">Catch the phish before it catches your people.</div>
        </div>
        <div className="login-main">
        <h1 className="login-title">{twoFactor ? "Two-step verification" : "Welcome back"}</h1>
        <p className="login-sub">
          {twoFactor
            ? "Enter the 6-digit code from your authenticator app."
            : "Sign in to run and track your awareness campaigns."}
        </p>

        <form onSubmit={submit}>
          {twoFactor ? (
            <div className="field">
              <label htmlFor="code">Authentication code</label>
              <input
                id="code"
                type="text"
                inputMode="numeric"
                autoComplete="one-time-code"
                autoFocus
                maxLength={6}
                placeholder="123456"
                value={code}
                onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
                required
              />
            </div>
          ) : (
            <>
              <div className="field">
                <label htmlFor="email">Email</label>
                <input
                  id="email"
                  type="email"
                  value={email}
                  autoComplete="username"
                  autoFocus
                  placeholder="you@company.com"
                  onChange={(e) => setEmail(e.target.value)}
                  required
                />
              </div>
              <div className="field">
                <label htmlFor="password">Password</label>
                <div className="pw-wrap">
                  <input
                    id="password"
                    type={show ? "text" : "password"}
                    value={password}
                    autoComplete="current-password"
                    placeholder="••••••••••••"
                    onChange={(e) => setPassword(e.target.value)}
                    required
                  />
                  <button type="button" className="pw-toggle" onClick={() => setShow((s) => !s)} tabIndex={-1}>
                    {show ? "Hide" : "Show"}
                  </button>
                </div>
              </div>
            </>
          )}
          {err && <div className="login-err">{err}</div>}
          <button className="login-btn" disabled={busy}>
            {busy ? "Signing in…" : twoFactor ? "Verify" : "Sign in"}
          </button>
          {twoFactor && (
            <button
              type="button"
              className="pw-toggle"
              style={{ position: "static", display: "block", margin: "12px auto 0" }}
              onClick={() => {
                setTwoFactor(false);
                setCode("");
                setErr(null);
              }}
            >
              ← Back
            </button>
          )}
        </form>

        {!twoFactor && sso?.enabled && (
          <>
            <div className="sso-divider"><span>or</span></div>
            <button type="button" className="login-btn sso-btn" onClick={() => { window.location.href = "/api/v1/auth/oidc/login"; }}>
              🔐 {sso.button_label}
            </button>
          </>
        )}
        </div>
      </div>
      <div className="login-foot">Authorized security-awareness training only.</div>
    </div>
  );
}
