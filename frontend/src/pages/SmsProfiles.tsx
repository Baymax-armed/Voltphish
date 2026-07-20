import { useEffect, useState } from "react";
import { api, ApiError } from "../api";
import type { SmsProfile, SmsProviderKind } from "../types";
import { Empty, ListSkeleton, Modal } from "../components/ui";
import { confirmDialog } from "../components/dialog";
import { useToast } from "../components/Toast";

const PROVIDERS: { value: SmsProviderKind; label: string; note: string }[] = [
  { value: "textbelt", label: "TextBelt — FREE, no signup", note: "Works instantly: leave the key blank to use the free tier (1 SMS/day). For more, buy a TextBelt key and paste it — no account setup needed." },
  { value: "generic", label: "Indian gateway (MSG91 / Fast2SMS / Gupshup)", note: "Cheap real SMS. Sign up (free trial credits), then paste a JSON config with url + body using {phone} {message} {secret}." },
  { value: "twilio", label: "Twilio", note: "Needs Account SID (account), Auth Token (secret), and a From number." },
];

const GENERIC_EXAMPLE = `{
  "url": "https://www.fast2sms.com/dev/bulkV2",
  "method": "POST",
  "json": false,
  "headers": { "authorization": "{secret}" },
  "body": { "route": "q", "message": "{message}", "numbers": "{phone}" }
}`;

export default function SmsProfiles() {
  const { notify } = useToast();
  const [items, setItems] = useState<SmsProfile[] | null>(null);
  const [editing, setEditing] = useState<SmsProfile | null>(null);
  const [creating, setCreating] = useState(false);
  const [verifying, setVerifying] = useState<number | null>(null);
  const [testing, setTesting] = useState<SmsProfile | null>(null);

  const load = () => api.listSmsProfiles().then(setItems);
  useEffect(() => {
    load();
  }, []);

  const remove = async (p: SmsProfile) => {
    if (!(await confirmDialog({ title: "Delete SMS profile", message: `Delete "${p.name}"?`, confirmLabel: "Delete", danger: true }))) return;
    try {
      await api.deleteSmsProfile(p.id);
      notify("Deleted");
      load();
    } catch (e) {
      notify(e instanceof ApiError ? e.message : "Delete failed", "error");
    }
  };

  const verify = async (p: SmsProfile) => {
    setVerifying(p.id);
    try {
      notify((await api.verifySmsProfile(p.id)).detail, "ok");
    } catch (e) {
      notify(e instanceof ApiError ? e.message : "Verify failed", "error");
    } finally {
      setVerifying(null);
    }
  };

  if (!items) return <ListSkeleton cols={4} />;

  return (
    <>
      <div className="page-head">
        <div>
          <h1>SMS Profiles</h1>
          <div className="page-sub">Gateways for SMS (smishing) campaigns — text + tracking link</div>
        </div>
        <button className="btn primary" onClick={() => setCreating(true)}>
          + New SMS profile
        </button>
      </div>

      <div className="banner">
        📱 <strong>TextBelt</strong> is free and needs no signup — create a TextBelt profile with a blank key and it
        sends real SMS right away (1/day on the free tier). For volume, use an Indian gateway (Fast2SMS / MSG91) via
        the Generic option. Use <strong>Send test</strong> to fire a real SMS to your own number.
      </div>

      {items.length === 0 ? (
        <div className="card">
          <Empty>No SMS profiles yet.</Empty>
        </div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Provider</th>
                <th>From</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {items.map((p) => (
                <tr key={p.id}>
                  <td>
                    <strong>{p.name}</strong>
                  </td>
                  <td>{p.provider}</td>
                  <td className="mono">{p.from_number || "—"}</td>
                  <td>
                    <div className="btn-row">
                      <button className="btn sm" onClick={() => verify(p)} disabled={verifying === p.id}>
                        {verifying === p.id ? "…" : "✓ Verify"}
                      </button>
                      <button className="btn sm" onClick={() => setTesting(p)}>
                        Send test
                      </button>
                      <button className="btn sm" onClick={() => setEditing(p)}>
                        Edit
                      </button>
                      <button className="btn sm danger" onClick={() => remove(p)}>
                        Delete
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {(creating || editing) && (
        <SmsForm
          profile={editing}
          onClose={() => {
            setCreating(false);
            setEditing(null);
          }}
          onSaved={() => {
            setCreating(false);
            setEditing(null);
            load();
          }}
        />
      )}
      {testing && <SmsTest profile={testing} onClose={() => setTesting(null)} />}
    </>
  );
}

function SmsForm({ profile, onClose, onSaved }: { profile: SmsProfile | null; onClose: () => void; onSaved: () => void }) {
  const { notify } = useToast();
  const [provider, setProvider] = useState<SmsProviderKind>(profile?.provider ?? "textbelt");
  const [name, setName] = useState(profile?.name ?? "");
  const [from, setFrom] = useState(profile?.from_number ?? "");
  const [account, setAccount] = useState(profile?.account ?? "");
  const [secret, setSecret] = useState("");
  const [config, setConfig] = useState(profile?.config ?? GENERIC_EXAMPLE);
  const [busy, setBusy] = useState(false);
  const note = PROVIDERS.find((p) => p.value === provider)?.note;

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    const payload: Record<string, unknown> = {
      name, provider,
      from_number: from || null,
      account: account || null,
      config: provider === "generic" ? config : null,
    };
    if (secret) payload.secret = secret;
    try {
      if (profile) await api.updateSmsProfile(profile.id, payload);
      else await api.createSmsProfile(payload);
      notify("SMS profile saved");
      onSaved();
    } catch (e) {
      notify(e instanceof ApiError ? e.message : "Save failed", "error");
      setBusy(false);
    }
  };

  return (
    <Modal title={profile ? "Edit SMS profile" : "New SMS profile"} onClose={onClose} wide={provider === "generic"}>
      <form onSubmit={save}>
        <div className="field">
          <label>Provider</label>
          <select value={provider} onChange={(e) => setProvider(e.target.value as SmsProviderKind)}>
            {PROVIDERS.map((p) => (
              <option key={p.value} value={p.value}>
                {p.label}
              </option>
            ))}
          </select>
          {note && <span className="hint">{note}</span>}
        </div>
        <div className="field">
          <label>Name</label>
          <input value={name} onChange={(e) => setName(e.target.value)} required />
        </div>
        {provider !== "console" && (
          <div className="field">
            <label>From / Sender ID <span className="hint">(number or short sender name)</span></label>
            <input value={from} onChange={(e) => setFrom(e.target.value)} placeholder="+1555… or COMPANY" />
          </div>
        )}
        {provider === "twilio" && (
          <div className="field">
            <label>Account SID</label>
            <input value={account} onChange={(e) => setAccount(e.target.value)} placeholder="ACxxxxxxxx" />
          </div>
        )}
        {(provider === "twilio" || provider === "textbelt" || provider === "generic") && (
          <div className="field">
            <label>
              {provider === "twilio" ? "Auth Token" : provider === "textbelt" ? "API key" : "Secret / API key"}{" "}
              <span className="hint">{profile?.has_secret ? "(leave blank to keep)" : provider === "textbelt" ? "(blank = free 1/day)" : ""}</span>
            </label>
            <input type="password" value={secret} autoComplete="new-password" onChange={(e) => setSecret(e.target.value)} />
          </div>
        )}
        {provider === "generic" && (
          <div className="field">
            <label>Gateway config (JSON) <span className="hint">use {"{phone} {message} {secret} {from}"}</span></label>
            <textarea value={config} onChange={(e) => setConfig(e.target.value)} rows={9} />
          </div>
        )}
        <div className="btn-row" style={{ justifyContent: "flex-end" }}>
          <button type="button" className="btn" onClick={onClose}>
            Cancel
          </button>
          <button className="btn primary" disabled={busy}>
            {busy ? "Saving…" : "Save profile"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

function SmsTest({ profile, onClose }: { profile: SmsProfile; onClose: () => void }) {
  const { notify } = useToast();
  const [to, setTo] = useState("");
  const [msg, setMsg] = useState("VoltPhish test message");
  const [busy, setBusy] = useState(false);

  const send = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      notify((await api.testSmsProfile(profile.id, to, msg)).detail, "ok");
      onClose();
    } catch (e) {
      notify(e instanceof ApiError ? e.message : "Send failed", "error");
      setBusy(false);
    }
  };

  return (
    <Modal title={`Send test SMS — ${profile.name}`} onClose={onClose}>
      <form onSubmit={send}>
        <div className="field">
          <label>To (phone)</label>
          <input value={to} onChange={(e) => setTo(e.target.value)} placeholder="+15551234567" required />
        </div>
        <div className="field">
          <label>Message</label>
          <textarea value={msg} onChange={(e) => setMsg(e.target.value)} rows={3} />
        </div>
        <div className="btn-row" style={{ justifyContent: "flex-end" }}>
          <button type="button" className="btn" onClick={onClose}>
            Cancel
          </button>
          <button className="btn primary" disabled={busy}>
            {busy ? "Sending…" : "Send test SMS"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
