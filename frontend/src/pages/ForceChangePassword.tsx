import { useState } from "react";
import { api, ApiError } from "../api";
import { useAuth } from "../auth";
import { useToast } from "../components/Toast";

// Full-screen gate shown right after login when the account is on a temporary
// password (generated first-run password, or an admin reset). The rest of the
// app stays hidden until a new password is set.
export default function ForceChangePassword() {
  const { user, refreshUser, logout } = useAuth();
  const { notify } = useToast();
  const [cur, setCur] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErr(null);
    if (next !== confirm) {
      setErr("New passwords don't match");
      return;
    }
    setBusy(true);
    try {
      await api.changePassword(cur, next);
      notify("Password updated");
      await refreshUser(); // clears must_change_password -> app loads
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Could not change password");
      setBusy(false);
    }
  };

  return (
    <div className="login-wrap">
      <div className="card login-card">
        <div className="brand">
          <div className="brand-logo">P</div>
          <div>
            <div className="brand-name">Set a new password</div>
            <div className="brand-tag">{user?.email}</div>
          </div>
        </div>
        <div className="banner" style={{ marginBottom: 16 }}>
          You're signed in with a temporary password. Choose a new one to continue.
        </div>
        <form onSubmit={submit}>
          <div className="field">
            <label>Current (temporary) password</label>
            <input type="password" value={cur} autoComplete="current-password" onChange={(e) => setCur(e.target.value)} required />
          </div>
          <div className="field">
            <label>New password <span className="hint">(min 12 characters)</span></label>
            <input type="password" value={next} autoComplete="new-password" minLength={12} onChange={(e) => setNext(e.target.value)} required />
          </div>
          <div className="field">
            <label>Confirm new password</label>
            <input type="password" value={confirm} autoComplete="new-password" minLength={12} onChange={(e) => setConfirm(e.target.value)} required />
          </div>
          {err && <div className="err">{err}</div>}
          <button className="btn primary" style={{ width: "100%", marginTop: 8 }} disabled={busy}>
            {busy ? "Saving…" : "Set password & continue"}
          </button>
        </form>
        <button className="btn sm" style={{ width: "100%", marginTop: 10 }} onClick={() => logout()}>
          Sign out
        </button>
      </div>
    </div>
  );
}
