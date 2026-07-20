import { useEffect, useState } from "react";
import { api, ApiError } from "../api";
import type { ApiKey } from "../types";
import { BulkBar, Empty, ListSkeleton, Modal, fmtDate, useSelection } from "../components/ui";
import { confirmDialog } from "../components/dialog";
import { useToast } from "../components/Toast";

export default function ApiKeys() {
  const { notify } = useToast();
  const [items, setItems] = useState<ApiKey[] | null>(null);
  const [creating, setCreating] = useState(false);
  const [newKey, setNewKey] = useState<string | null>(null);
  const { sel, toggle, clear, allToggle } = useSelection();

  const load = () => api.listApiKeys().then(setItems);
  useEffect(() => {
    load();
  }, []);

  const revoke = async (k: ApiKey) => {
    if (!(await confirmDialog({ title: "Revoke key", message: `Revoke "${k.name}"? Anything using it will stop working.`, confirmLabel: "Revoke", danger: true }))) return;
    try {
      await api.revokeApiKey(k.id);
      notify("Key revoked");
      load();
    } catch (e) {
      notify(e instanceof ApiError ? e.message : "Revoke failed", "error");
    }
  };

  const bulkRevoke = async () => {
    if (!(await confirmDialog({ title: "Revoke keys", message: `Revoke ${sel.size} key${sel.size > 1 ? "s" : ""}? Anything using them will stop working.`, confirmLabel: "Revoke", danger: true }))) return;
    let ok = 0;
    let fail = 0;
    for (const id of sel) {
      try {
        await api.revokeApiKey(id);
        ok++;
      } catch {
        fail++;
      }
    }
    notify(fail ? `Revoked ${ok}; ${fail} failed.` : `Revoked ${ok} key${ok > 1 ? "s" : ""}.`, fail ? "error" : "ok");
    clear();
    load();
  };

  if (!items) return <ListSkeleton cols={4} />;
  const ids = items.map((k) => k.id);
  const allChecked = ids.length > 0 && ids.every((id) => sel.has(id));

  return (
    <>
      <div className="page-head">
        <div>
          <h1>API Keys</h1>
          <div className="page-sub">
            Programmatic access to the REST API. Send{" "}
            <span className="mono">Authorization: Bearer &lt;key&gt;</span>.
          </div>
        </div>
        <button className="btn primary" onClick={() => setCreating(true)}>
          + New API key
        </button>
      </div>

      <BulkBar count={sel.size} noun="key" onDelete={bulkRevoke} onClear={clear} />

      {items.length === 0 ? (
        <div className="card">
          <Empty>No API keys yet.</Empty>
        </div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th className="check-col">
                  <input
                    type="checkbox"
                    aria-label="Select all"
                    checked={allChecked}
                    ref={(el) => {
                      if (el) el.indeterminate = sel.size > 0 && !allChecked;
                    }}
                    onChange={() => allToggle(ids)}
                  />
                </th>
                <th>Name</th>
                <th>Prefix</th>
                <th>Last used</th>
                <th>Created</th>
                <th className="actions-col"></th>
              </tr>
            </thead>
            <tbody>
              {items.map((k) => (
                <tr key={k.id} className={sel.has(k.id) ? "selected" : ""}>
                  <td className="check-col">
                    <input type="checkbox" aria-label={`Select ${k.name}`} checked={sel.has(k.id)} onChange={() => toggle(k.id)} />
                  </td>
                  <td>
                    <strong>{k.name}</strong>
                  </td>
                  <td className="mono">{k.prefix}…</td>
                  <td>{fmtDate(k.last_used_at)}</td>
                  <td>{fmtDate(k.created_at)}</td>
                  <td className="actions-col">
                    <button className="btn sm danger" onClick={() => revoke(k)}>
                      Revoke
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {creating && (
        <CreateKey
          onClose={() => setCreating(false)}
          onCreated={(key) => {
            setCreating(false);
            setNewKey(key);
            load();
          }}
        />
      )}

      {newKey && (
        <Modal title="Copy your API key now" onClose={() => setNewKey(null)}>
          <p className="page-sub" style={{ marginTop: 0 }}>
            This is the only time the full key is shown. Store it somewhere safe.
          </p>
          <div className="card mono" style={{ wordBreak: "break-all", userSelect: "all" }}>{newKey}</div>
          <div className="btn-row" style={{ justifyContent: "flex-end", marginTop: 14 }}>
            <button
              className="btn"
              onClick={() => {
                navigator.clipboard?.writeText(newKey);
                notify("Copied");
              }}
            >
              Copy
            </button>
            <button className="btn primary" onClick={() => setNewKey(null)}>
              Done
            </button>
          </div>
        </Modal>
      )}
    </>
  );
}

function CreateKey({ onClose, onCreated }: { onClose: () => void; onCreated: (key: string) => void }) {
  const { notify } = useToast();
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      const created = await api.createApiKey(name);
      onCreated(created.key);
    } catch (e) {
      notify(e instanceof ApiError ? e.message : "Create failed", "error");
      setBusy(false);
    }
  };

  return (
    <Modal title="New API key" onClose={onClose}>
      <form onSubmit={save}>
        <div className="field">
          <label>Name <span className="hint">(what will use this key)</span></label>
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="CI pipeline" required />
        </div>
        <div className="btn-row" style={{ justifyContent: "flex-end" }}>
          <button type="button" className="btn" onClick={onClose}>
            Cancel
          </button>
          <button className="btn primary" disabled={busy}>
            {busy ? "Creating…" : "Create key"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
