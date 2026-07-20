import { useState } from "react";
import { useAuth } from "../auth";
import { ApiError } from "../api";

export default function Login() {
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErr(null);
    setBusy(true);
    try {
      await login(email, password);
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
        <h1 className="login-title">Welcome back</h1>
        <p className="login-sub">Sign in to run and track your awareness campaigns.</p>

        <form onSubmit={submit}>
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
          {err && <div className="login-err">{err}</div>}
          <button className="login-btn" disabled={busy}>
            {busy ? "Signing in…" : "Sign in"}
          </button>
        </form>
        </div>
      </div>
      <div className="login-foot">Authorized security-awareness training only.</div>
    </div>
  );
}
