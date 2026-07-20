import { useState } from "react";
import { api, ApiError } from "../api";
import { Modal } from "./ui";
import { useToast } from "./Toast";

export default function ChangePassword({ onClose }: { onClose: () => void }) {
  const { notify } = useToast();
  const [cur, setCur] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    if (next !== confirm) {
      notify("New passwords don't match", "error");
      return;
    }
    setBusy(true);
    try {
      await api.changePassword(cur, next);
      notify("Password changed");
      onClose();
    } catch (e) {
      notify(e instanceof ApiError ? e.message : "Change failed", "error");
      setBusy(false);
    }
  };

  return (
    <Modal title="Change password" onClose={onClose}>
      <form onSubmit={save}>
        <div className="field">
          <label>Current password</label>
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
        <div className="btn-row" style={{ justifyContent: "flex-end" }}>
          <button type="button" className="btn" onClick={onClose}>
            Cancel
          </button>
          <button className="btn primary" disabled={busy}>
            {busy ? "Saving…" : "Change password"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
