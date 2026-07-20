import { useEffect, useState } from "react";
import { api, ApiError } from "../api";
import type { Webhook } from "../types";
import { Badge, BulkBar, CopyButton, Empty, ListSkeleton, Modal, RowMenu, useSelection } from "../components/ui";
import { confirmDialog } from "../components/dialog";
import { useToast } from "../components/Toast";

export default function Webhooks() {
  const { notify } = useToast();
  const [items, setItems] = useState<Webhook[] | null>(null);
  const [editing, setEditing] = useState<Webhook | null>(null);
  const [creating, setCreating] = useState(false);
  const [testing, setTesting] = useState<number | null>(null);
  const { sel, toggle, clear, allToggle } = useSelection();

  const load = () => api.listWebhooks().then(setItems);
  useEffect(() => {
    load();
  }, []);

  const bulkDelete = async () => {
    if (!(await confirmDialog({ title: "Delete webhooks", message: `Delete ${sel.size} webhook${sel.size > 1 ? "s" : ""}?`, confirmLabel: "Delete", danger: true }))) return;
    let ok = 0;
    let fail = 0;
    for (const id of sel) {
      try {
        await api.deleteWebhook(id);
        ok++;
      } catch {
        fail++;
      }
    }
    notify(fail ? `Deleted ${ok}; ${fail} failed.` : `Deleted ${ok} webhook${ok > 1 ? "s" : ""}.`, fail ? "error" : "ok");
    clear();
    load();
  };

  const sendTest = async (w: Webhook) => {
    setTesting(w.id);
    try {
      const r = await api.testWebhook(w.id);
      notify(r.detail, "ok");
    } catch (e) {
      notify(e instanceof ApiError ? e.message : "Test failed", "error");
    } finally {
      setTesting(null);
    }
  };

  const remove = async (w: Webhook) => {
    if (!(await confirmDialog({ title: "Delete webhook", message: `Delete "${w.name}"?`, confirmLabel: "Delete", danger: true }))) return;
    try {
      await api.deleteWebhook(w.id);
      notify("Webhook deleted");
      load();
    } catch (e) {
      notify(e instanceof ApiError ? e.message : "Delete failed", "error");
    }
  };

  if (!items) return <ListSkeleton cols={5} />;
  const ids = items.map((w) => w.id);
  const allChecked = ids.length > 0 && ids.every((id) => sel.has(id));

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Webhooks</h1>
          <div className="page-sub">
            POST campaign events (sent, opened, clicked, submitted, reported) to external systems
          </div>
        </div>
        <button className="btn primary" onClick={() => setCreating(true)}>
          + New webhook
        </button>
      </div>

      <div className="banner">
        🔐 Generic deliveries are HMAC-SHA256 signed (<span className="mono">X-VoltPhish-Signature</span>).
        Pick <strong>Slack</strong> or <strong>Teams</strong> format to get instant chat alerts the moment
        someone clicks or submits. All targets pass the SSRF guard; delivery retries via the durable job queue.
      </div>

      <BulkBar count={sel.size} noun="webhook" onDelete={bulkDelete} onClear={clear} />

      {items.length === 0 ? (
        <div className="card">
          <Empty>No webhooks yet.</Empty>
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
                <th>Format</th>
                <th>URL</th>
                <th>Secret</th>
                <th>Status</th>
                <th className="actions-col"></th>
              </tr>
            </thead>
            <tbody>
              {items.map((w) => (
                <tr key={w.id} className={sel.has(w.id) ? "selected" : ""}>
                  <td className="check-col">
                    <input type="checkbox" aria-label={`Select ${w.name}`} checked={sel.has(w.id)} onChange={() => toggle(w.id)} />
                  </td>
                  <td>
                    <strong>{w.name}</strong>
                  </td>
                  <td>{w.format === "slack" ? "💬 Slack" : w.format === "teams" ? "💬 Teams" : "JSON"}</td>
                  <td>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <span
                        className="mono"
                        title={w.url}
                        style={{ display: "inline-block", maxWidth: 300, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", verticalAlign: "middle", color: "var(--text-dim)" }}
                      >
                        {w.url}
                      </span>
                      <CopyButton text={w.url} label="Copy URL" />
                    </div>
                  </td>
                  <td>{w.has_secret ? "set" : "—"}</td>
                  <td>
                    <Badge status={w.is_active ? "completed" : "draft"} />
                  </td>
                  <td className="actions-col">
                    <div className="btn-row" style={{ justifyContent: "flex-end", flexWrap: "nowrap" }}>
                      <button className="btn sm" onClick={() => sendTest(w)} disabled={testing === w.id} title="Send a sample notification">
                        {testing === w.id ? "Testing…" : "📨 Test"}
                      </button>
                      <RowMenu
                        items={[
                          { label: "Edit", icon: "✎", onClick: () => setEditing(w) },
                          { label: "Delete", icon: "🗑", danger: true, onClick: () => remove(w) },
                        ]}
                      />
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {(creating || editing) && (
        <WebhookForm
          webhook={editing}
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
    </>
  );
}

function WebhookForm({
  webhook,
  onClose,
  onSaved,
}: {
  webhook: Webhook | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const { notify } = useToast();
  const [name, setName] = useState(webhook?.name ?? "");
  const [url, setUrl] = useState(webhook?.url ?? "");
  const [secret, setSecret] = useState("");
  const [format, setFormat] = useState(webhook?.format ?? "generic");
  const [active, setActive] = useState(webhook?.is_active ?? true);
  const [busy, setBusy] = useState(false);
  const isChat = format === "slack" || format === "teams";

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    const payload: Record<string, unknown> = { name, url, format, is_active: active };
    if (secret) payload.secret = secret;
    try {
      const saved = webhook ? await api.updateWebhook(webhook.id, payload) : await api.createWebhook(payload);
      notify("Webhook saved");
      // Auto-verify chat webhooks so the operator knows the URL actually works.
      try {
        const r = await api.testWebhook(saved.id);
        notify(`Verified — ${r.detail}`, "ok");
      } catch (te) {
        notify(`Saved, but the test didn't go through: ${te instanceof ApiError ? te.message : "error"}`, "error");
      }
      onSaved();
    } catch (e) {
      notify(e instanceof ApiError ? e.message : "Save failed", "error");
      setBusy(false);
    }
  };

  return (
    <Modal title={webhook ? "Edit webhook" : "New webhook"} onClose={onClose}>
      <form onSubmit={save}>
        <div className="field">
          <label>Name</label>
          <input value={name} onChange={(e) => setName(e.target.value)} required />
        </div>
        <div className="field">
          <label>Format</label>
          <select value={format} onChange={(e) => setFormat(e.target.value)}>
            <option value="generic">Generic — signed JSON to your endpoint</option>
            <option value="slack">Slack — real-time message to a channel</option>
            <option value="teams">Microsoft Teams — real-time message to a channel</option>
          </select>
          {isChat && (
            <span className="hint" style={{ marginTop: 6, display: "block" }}>
              Paste your {format === "slack" ? "Slack" : "Teams"} <strong>Incoming Webhook URL</strong> below.
              You'll get an instant chat alert on every open, click, submit &amp; report — no secret needed.
            </span>
          )}
        </div>
        <div className="field">
          <label>
            Payload URL{" "}
            <span className="hint">
              {isChat
                ? format === "slack"
                  ? "(https://hooks.slack.com/services/…)"
                  : "(https://…webhook.office.com/…)"
                : "(https recommended; no internal addresses)"}
            </span>
          </label>
          <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://example.com/hooks/phishsim" required />
          {format === "teams" && (
            <span className="hint" style={{ marginTop: 6, display: "block" }}>
              In Teams: channel <strong>···</strong> → <strong>Workflows</strong> → search <em>webhook</em> → pick{" "}
              <em>“Send webhook alerts to a channel”</em> → choose the channel → copy the URL
              (<span className="mono">…logic.azure.com…</span>). A <span className="mono">teams.microsoft.com/l/chat/…</span> link will <strong>not</strong> work.
            </span>
          )}
        </div>
        {!isChat && (
          <div className="field">
            <label>
              Signing secret <span className="hint">{webhook?.has_secret ? "(leave blank to keep)" : "(used for HMAC signature)"}</span>
            </label>
            <input type="password" value={secret} autoComplete="new-password" onChange={(e) => setSecret(e.target.value)} />
          </div>
        )}
        <div className="field check">
          <input id="wactive" type="checkbox" checked={active} onChange={(e) => setActive(e.target.checked)} />
          <label htmlFor="wactive">Active</label>
        </div>
        <div className="btn-row" style={{ justifyContent: "flex-end" }}>
          <button type="button" className="btn" onClick={onClose}>
            Cancel
          </button>
          <button className="btn primary" disabled={busy}>
            {busy ? "Saving & verifying…" : isChat ? "Save & send test" : "Save webhook"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
