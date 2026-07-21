import { useEffect, useState } from "react";
import { api, ApiError } from "../api";
import type { Attachment, Profile, Template } from "../types";
import { BulkBar, Empty, FormSkeleton, ListSkeleton, Modal, RowMenu, fmtDate, useSelection } from "../components/ui";
import { confirmDialog } from "../components/dialog";
import { useToast } from "../components/Toast";
import HtmlEditor from "../components/HtmlEditor";
import { GALLERY_TEMPLATES, type GalleryTemplate } from "../gallery";

const SAMPLE = `<p>Hi {{.FirstName}},</p>
<p>We detected unusual sign-in activity. Please
<a href="{{.URL}}">verify your account</a> within 24 hours.</p>
<p>— IT Support</p>`;

export default function Templates() {
  const { notify } = useToast();
  const [items, setItems] = useState<Template[] | null>(null);
  const [editing, setEditing] = useState<Template | null>(null);
  const [creating, setCreating] = useState(false);
  const [testing, setTesting] = useState<Template | null>(null);
  const [q, setQ] = useState("");
  const [gallery, setGallery] = useState(false);
  const { sel, toggle, clear, allToggle } = useSelection();

  const load = () => api.listTemplates().then(setItems);
  useEffect(() => {
    load();
  }, []);

  const bulkDelete = async () => {
    if (!(await confirmDialog({ title: "Delete templates", message: `Delete ${sel.size} template${sel.size > 1 ? "s" : ""}?`, confirmLabel: "Delete", danger: true }))) return;
    let ok = 0;
    let fail = 0;
    for (const id of sel) {
      try {
        await api.deleteTemplate(id);
        ok++;
      } catch {
        fail++;
      }
    }
    notify(fail ? `Deleted ${ok}; ${fail} still used by a campaign.` : `Deleted ${ok} template${ok > 1 ? "s" : ""}.`, fail ? "error" : "ok");
    clear();
    load();
  };

  const exportAll = () => {
    const data = (items ?? []).map((t) => ({
      name: t.name, channel: t.channel, subject: t.subject,
      envelope_sender: t.envelope_sender, html: t.html, text: t.text,
    }));
    const blob = new Blob([JSON.stringify({ voltphish_templates: data }, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "voltphish-templates.json";
    a.click();
    URL.revokeObjectURL(url);
  };

  const importFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    let list: Record<string, unknown>[];
    try {
      const parsed = JSON.parse(await file.text());
      list = Array.isArray(parsed) ? parsed : ((parsed.voltphish_templates ?? parsed.templates ?? [parsed]) as Record<string, unknown>[]);
    } catch {
      notify("That file isn't valid JSON.", "error");
      return;
    }
    const existing = new Set((items ?? []).map((t) => t.name.toLowerCase()));
    let ok = 0;
    let fail = 0;
    for (const t of list) {
      if (!t || typeof t.name !== "string") {
        fail++;
        continue;
      }
      let name = t.name;
      let n = 2;
      while (existing.has(name.toLowerCase())) name = `${t.name} ${n++}`;
      existing.add(name.toLowerCase());
      try {
        await api.createTemplate({
          name,
          channel: "email",
          subject: (t.subject as string) || "",
          envelope_sender: (t.envelope_sender as string) || null,
          html: (t.html as string) || null,
          text: (t.text as string) || null,
        });
        ok++;
      } catch {
        fail++;
      }
    }
    notify(fail ? `Imported ${ok}; ${fail} skipped.` : `Imported ${ok} template${ok > 1 ? "s" : ""}.`, fail ? "error" : "ok");
    load();
  };

  const useFromGallery = async (g: GalleryTemplate) => {
    try {
      const existing = new Set((items ?? []).map((t) => t.name));
      let name = g.name;
      let n = 2;
      while (existing.has(name)) name = `${g.name} ${n++}`;
      await api.createTemplate({ name, channel: "email", subject: g.subject, html: g.html, text: g.text });
      notify(`Added "${name}" — edit to customize`);
      setGallery(false);
      load();
    } catch (e) {
      notify(e instanceof ApiError ? e.message : "Failed", "error");
    }
  };

  const remove = async (t: Template) => {
    if (!(await confirmDialog({ title: "Delete template", message: `Delete "${t.name}"?`, confirmLabel: "Delete", danger: true }))) return;
    try {
      await api.deleteTemplate(t.id);
      notify("Template deleted");
      load();
    } catch (e) {
      notify(e instanceof ApiError ? e.message : "Delete failed", "error");
    }
  };

  const clone = async (t: Template) => {
    try {
      await api.createTemplate({
        name: `${t.name} (copy)`, channel: t.channel, subject: t.subject,
        envelope_sender: t.envelope_sender, html: t.html, text: t.text,
      });
      notify("Template cloned");
      load();
    } catch (e) {
      notify(e instanceof ApiError ? e.message : "Clone failed", "error");
    }
  };

  const filtered = items?.filter((t) => t.name.toLowerCase().includes(q.toLowerCase())) ?? [];
  const ids = filtered.map((t) => t.id);
  const allChecked = ids.length > 0 && ids.every((id) => sel.has(id));

  if (!items) return <ListSkeleton cols={4} />;

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Email Templates</h1>
          <div className="page-sub">
            Use <span className="mono">{"{{.FirstName}}"}</span>,{" "}
            <span className="mono">{"{{.URL}}"}</span> and more for personalization
          </div>
        </div>
        <div className="btn-row">
          <label className="btn" style={{ cursor: "pointer" }} title="Import templates from a .json file">
            ⭱ Import
            <input type="file" accept=".json,application/json" onChange={importFile} style={{ display: "none" }} />
          </label>
          <button className="btn" onClick={exportAll} disabled={!items?.length} title="Export all templates to a shareable .json file">
            ⭳ Export
          </button>
          <button className="btn" onClick={() => setGallery(true)}>
            📚 Gallery
          </button>
          <button className="btn primary" onClick={() => setCreating(true)}>
            + New template
          </button>
        </div>
      </div>

      {gallery && (
        <Modal title="Template gallery — one click to add" onClose={() => setGallery(false)} wide>
          <div className="grid cols-2" style={{ gap: 12 }}>
            {GALLERY_TEMPLATES.map((g) => (
              <div className="card hover" key={g.name} style={{ cursor: "pointer" }} onClick={() => useFromGallery(g)}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                  <strong>{g.name}</strong>
                  <span className="badge scheduled">{g.category}</span>
                </div>
                <div className="hint" style={{ marginBottom: 8 }}>Subject: {g.subject}</div>
                <div style={{ height: 140, overflow: "hidden", border: "1px solid var(--border)", borderRadius: 8, pointerEvents: "none", background: "#fff" }}>
                  <iframe title={g.name} sandbox="" style={{ width: "100%", height: 260, border: 0, display: "block" }}
                    srcDoc={"<style>html{zoom:0.62}body{margin:0}</style>" + g.html.replace(/\{\{\.FirstName\}\}/g, "Alex").replace(/\{\{\.URL\}\}/g, "#")} />
                </div>
              </div>
            ))}
          </div>
        </Modal>
      )}

      {items.length > 0 && (
        <input className="search-box" placeholder="Search templates…" value={q} onChange={(e) => setQ(e.target.value)} />
      )}

      <BulkBar count={sel.size} noun="template" onDelete={bulkDelete} onClear={clear} />

      {items.length === 0 ? (
        <div className="card">
          <Empty>No templates yet. Create one to start building a campaign.</Empty>
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
                <th>Subject</th>
                <th>Bodies</th>
                <th>Modified</th>
                <th className="actions-col"></th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((t) => (
                <tr key={t.id} className={sel.has(t.id) ? "selected" : ""}>
                  <td className="check-col">
                    <input type="checkbox" aria-label={`Select ${t.name}`} checked={sel.has(t.id)} onChange={() => toggle(t.id)} />
                  </td>
                  <td>
                    <strong>{t.name}</strong>
                  </td>
                  <td>{t.subject}</td>
                  <td>{[t.html && "HTML", t.text && "Text"].filter(Boolean).join(" + ")}</td>
                  <td>{fmtDate(t.modified_at)}</td>
                  <td className="actions-col">
                    <RowMenu
                      items={[
                        { label: "Edit", icon: "✎", onClick: () => setEditing(t) },
                        { label: "Send test", icon: "✈", onClick: () => setTesting(t) },
                        { label: "Clone", icon: "⧉", onClick: () => clone(t) },
                        { label: "Delete", icon: "🗑", danger: true, onClick: () => remove(t) },
                      ]}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {(creating || editing) && (
        <TemplateForm
          template={editing}
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

      {testing && <SendTestForm template={testing} onClose={() => setTesting(null)} />}
    </>
  );
}

function SendTestForm({ template, onClose }: { template: Template; onClose: () => void }) {
  const { notify } = useToast();
  const [profiles, setProfiles] = useState<Profile[] | null>(null);
  const [profileId, setProfileId] = useState(0);
  const [email, setEmail] = useState("");
  const [firstName, setFirstName] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.listProfiles().then((p) => {
      setProfiles(p);
      setProfileId(p[0]?.id ?? 0);
    });
  }, []);

  const send = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      const res = await api.sendTestEmail({
        profile_id: profileId,
        template_id: template.id,
        to_email: email,
        first_name: firstName || null,
      });
      notify(res.detail);
      onClose();
    } catch (e) {
      notify(e instanceof ApiError ? e.message : "Send failed", "error");
      setBusy(false);
    }
  };

  return (
    <Modal title={`Send test — ${template.name}`} onClose={onClose}>
      {!profiles ? (
        <FormSkeleton fields={3} />
      ) : profiles.length === 0 ? (
        <Empty>Create a sending profile first.</Empty>
      ) : (
        <form onSubmit={send}>
          <div className="field">
            <label>Sending profile</label>
            <select value={profileId} onChange={(e) => setProfileId(Number(e.target.value))}>
              {profiles.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} ({p.host})
                </option>
              ))}
            </select>
          </div>
          <div className="row2">
            <div className="field">
              <label>Send to</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                required
              />
            </div>
            <div className="field">
              <label>First name <span className="hint">(for {"{{.FirstName}}"})</span></label>
              <input value={firstName} onChange={(e) => setFirstName(e.target.value)} placeholder="Alex" />
            </div>
          </div>
          <div className="btn-row" style={{ justifyContent: "flex-end" }}>
            <button type="button" className="btn" onClick={onClose}>
              Cancel
            </button>
            <button className="btn primary" disabled={busy}>
              {busy ? "Sending…" : "Send test email"}
            </button>
          </div>
        </form>
      )}
    </Modal>
  );
}

function TemplateForm({
  template,
  onClose,
  onSaved,
}: {
  template: Template | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const { notify } = useToast();
  const [name, setName] = useState(template?.name ?? "");
  const [subject, setSubject] = useState(template?.subject ?? "");
  const [sender, setSender] = useState(template?.envelope_sender ?? "");
  const [html, setHtml] = useState(template?.html ?? SAMPLE);
  const [text, setText] = useState(template?.text ?? "");
  const [busy, setBusy] = useState(false);
  const [bodyTab, setBodyTab] = useState<"html" | "text">("html");
  const [importOpen, setImportOpen] = useState(false);
  const [raw, setRaw] = useState("");
  const [aiOpen, setAiOpen] = useState(false);
  const [attachments, setAttachments] = useState<Attachment[]>(template?.attachments ?? []);
  const [icsOpen, setIcsOpen] = useState(false);

  const addIcs = async (ics: string, filename: string) => {
    if (!template) return;
    const b64 = btoa(unescape(encodeURIComponent(ics)));
    try {
      const att = await api.addAttachment(template.id, { filename, content_type: "text/calendar", content_b64: b64 });
      setAttachments((a) => [...a, att]);
      notify("Calendar invite attached — {{.URL}} becomes each recipient's link");
      setIcsOpen(false);
    } catch (e) {
      notify(e instanceof ApiError ? e.message : "Failed to attach", "error");
    }
  };

  const addTrackedDoc = async () => {
    if (!template) return;
    const html =
      '<!doctype html><html><head><meta charset="utf-8"><title>Document</title></head>' +
      '<body style="font-family:Segoe UI,Arial,sans-serif;max-width:640px;margin:40px auto;color:#222">' +
      "<h2>Confidential document — {{.FirstName}}</h2>" +
      "<p>For security, the full document opens in your verified browser session. Click below to view it:</p>" +
      '<p><a href="{{.URL}}" style="display:inline-block;background:#0067b8;color:#fff;text-decoration:none;padding:10px 22px;border-radius:5px">View secure document</a></p>' +
      '<p style="color:#888;font-size:12px">Document ref: {{.RId}}</p>' +
      "{{.AttachTracker}}</body></html>";
    const b64 = btoa(unescape(encodeURIComponent(html)));
    try {
      const att = await api.addAttachment(template.id, { filename: "document.html", content_type: "text/html", content_b64: b64 });
      setAttachments((a) => [...a, att]);
      notify("Tracked document attached — opening it records 'attachment opened'");
    } catch (e) {
      notify(e instanceof ApiError ? e.message : "Failed to attach", "error");
    }
  };

  const applyAi = (t: { name: string; subject: string; html: string | null; text: string | null }) => {
    if (!name.trim()) setName(t.name);
    setSubject(t.subject);
    if (t.html) { setHtml(t.html); setBodyTab("html"); }
    if (t.text) setText(t.text);
    setAiOpen(false);
    notify("AI draft applied — review and save");
  };

  const onPickFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file || !template) return;
    if (file.size > 5 * 1024 * 1024) {
      notify("File exceeds 5 MB limit", "error");
      return;
    }
    const b64 = await new Promise<string>((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result).split(",")[1] ?? "");
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });
    try {
      const att = await api.addAttachment(template.id, {
        filename: file.name,
        content_type: file.type || "application/octet-stream",
        content_b64: b64,
      });
      setAttachments((a) => [...a, att]);
      notify("Attachment added");
    } catch (err) {
      notify(err instanceof ApiError ? err.message : "Upload failed", "error");
    }
  };

  const removeAttachment = async (att: Attachment) => {
    if (!template) return;
    try {
      await api.deleteAttachment(template.id, att.id);
      setAttachments((a) => a.filter((x) => x.id !== att.id));
      notify("Attachment removed");
    } catch (err) {
      notify(err instanceof ApiError ? err.message : "Delete failed", "error");
    }
  };

  const doImport = async () => {
    try {
      const res = await api.importTemplate(raw);
      setSubject(res.subject);
      if (res.envelope_sender) setSender(res.envelope_sender);
      if (res.html) setHtml(res.html);
      if (res.text) setText(res.text);
      setImportOpen(false);
      setRaw("");
      notify("Imported — review and save");
    } catch (e) {
      notify(e instanceof ApiError ? e.message : "Import failed", "error");
    }
  };

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    const payload = { name, channel: "email" as const, subject, envelope_sender: sender || null, html: html || null, text: text || null };
    try {
      if (template) await api.updateTemplate(template.id, payload);
      else await api.createTemplate(payload);
      notify("Template saved");
      onSaved();
    } catch (e) {
      notify(e instanceof ApiError ? e.message : "Save failed", "error");
      setBusy(false);
    }
  };

  return (
    <Modal title={template ? "Edit template" : "New template"} onClose={onClose} wide>
      <div className="btn-row" style={{ justifyContent: "flex-end", marginBottom: 10 }}>
        <button type="button" className="btn sm primary" onClick={() => setAiOpen(true)}>
          ✨ Generate with AI
        </button>
        <button type="button" className="btn sm" onClick={() => setImportOpen((v) => !v)}>
          {importOpen ? "Close import" : "⭱ Import from .eml"}
        </button>
      </div>
      {importOpen && (
        <div className="card" style={{ marginBottom: 14 }}>
          <div className="field">
            <label>Paste a raw email (headers + body), then import</label>
            <textarea value={raw} onChange={(e) => setRaw(e.target.value)} rows={6}
              placeholder={"From: it@example.com\nSubject: ...\nContent-Type: text/html\n\n<p>...</p>"} />
          </div>
          <button type="button" className="btn primary sm" onClick={doImport} disabled={!raw.trim()}>
            Import into form
          </button>
        </div>
      )}
      {aiOpen && <AiGenerateModal onApply={applyAi} onClose={() => setAiOpen(false)} />}
      <form onSubmit={save}>
        <div className="field">
          <label>Template name</label>
          <input value={name} onChange={(e) => setName(e.target.value)} required />
        </div>

        <div className="row2">
          <div className="field">
            <label>Subject</label>
            <input value={subject} onChange={(e) => setSubject(e.target.value)} required />
          </div>
          <div className="field">
            <label>Envelope sender <span className="hint">(optional)</span></label>
            <input type="email" placeholder="it-support@example.com" value={sender} onChange={(e) => setSender(e.target.value)} />
          </div>
        </div>
        <div className="field">
          <label>Email body</label>
          <div className="tabs">
            <button type="button" className={`tab ${bodyTab === "html" ? "active" : ""}`} onClick={() => setBodyTab("html")}>
              HTML
            </button>
            <button type="button" className={`tab ${bodyTab === "text" ? "active" : ""}`} onClick={() => setBodyTab("text")}>
              Plain Text
            </button>
          </div>
          {bodyTab === "html" ? (
            <HtmlEditor value={html} onChange={setHtml} />
          ) : (
            <>
              <textarea value={text} onChange={(e) => setText(e.target.value)} rows={10}
                placeholder={"Hi {{.FirstName}}, verify your account: {{.URL}}"} />
              <span className="hint">
                Plain-text version (shown by clients that can't render HTML). Tokens work here too:{" "}
                {"{{.FirstName}} {{.URL}}"}.
              </span>
            </>
          )}
        </div>

        {(
        <div className="field">
          <label>Attachments <span className="hint">(lure documents; max 5 MB each, benign types only)</span></label>
          {!template ? (
            <div className="hint">Save the template first, then reopen it to add attachments.</div>
          ) : (
            <>
              {attachments.length > 0 && (
                <div className="table-wrap" style={{ marginBottom: 8 }}>
                  <table>
                    <tbody>
                      {attachments.map((a) => (
                        <tr key={a.id}>
                          <td className="mono">{a.filename}</td>
                          <td>{(a.size / 1024).toFixed(1)} KB</td>
                          <td style={{ width: 40 }}>
                            <button type="button" className="btn sm danger" onClick={() => removeAttachment(a)}>
                              ✕
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
                <input type="file" onChange={onPickFile} />
                <button type="button" className="btn sm" onClick={() => setIcsOpen(true)}>
                  📅 Add calendar invite
                </button>
                <button type="button" className="btn sm" onClick={addTrackedDoc} title="An HTML document that records when it's opened">
                  📎 Add tracked document
                </button>
              </div>
            </>
          )}
        </div>
        )}
        {icsOpen && <IcsModal onAdd={addIcs} onClose={() => setIcsOpen(false)} />}

        <div className="btn-row" style={{ justifyContent: "flex-end" }}>
          <button type="button" className="btn" onClick={onClose}>
            Cancel
          </button>
          <button className="btn primary" disabled={busy}>
            {busy ? "Saving…" : "Save template"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

function AiGenerateModal({
  onApply,
  onClose,
}: {
  onApply: (t: { name: string; subject: string; html: string | null; text: string | null }) => void;
  onClose: () => void;
}) {
  const { notify } = useToast();
  const [scenario, setScenario] = useState("");
  const [difficulty, setDifficulty] = useState("medium");
  const [busy, setBusy] = useState(false);

  const EXAMPLES = [
    "IT helpdesk asking staff to re-verify their mailbox before a migration this weekend",
    "HR announcing a revised salary structure — click to view your new package",
    "Courier company saying a parcel is held pending a delivery-fee payment",
    "Finance requesting approval of a pending vendor invoice",
  ];

  const generate = async () => {
    setBusy(true);
    try {
      const t = await api.aiGenerateTemplate(scenario, difficulty);
      onApply(t);
    } catch (e) {
      notify(e instanceof ApiError ? e.message : "AI generation failed", "error");
      setBusy(false);
    }
  };

  return (
    <Modal title="✨ Generate email with AI" onClose={onClose}>
      <div className="field">
        <label>
          Describe the scenario{" "}
          <span className="hint">the AI writes a simulation email using {"{{.FirstName}}"} and {"{{.URL}}"}</span>
        </label>
        <textarea
          value={scenario}
          onChange={(e) => setScenario(e.target.value)}
          rows={4}
          placeholder="e.g. IT helpdesk asking staff to re-verify their mailbox before a weekend migration"
          autoFocus
        />
      </div>
      <div className="field">
        <label>Try an example</label>
        <div className="btn-row" style={{ flexWrap: "wrap", gap: 6 }}>
          {EXAMPLES.map((ex) => (
            <button key={ex} type="button" className="btn sm" onClick={() => setScenario(ex)} title={ex}>
              {ex.length > 34 ? ex.slice(0, 34) + "…" : ex}
            </button>
          ))}
        </div>
      </div>
      <div className="field">
        <label>Difficulty</label>
        <select value={difficulty} onChange={(e) => setDifficulty(e.target.value)}>
          <option value="easy">Easy — obvious red flags</option>
          <option value="medium">Medium — believable pretext</option>
          <option value="hard">Hard — highly convincing, subtle cues</option>
        </select>
      </div>
      <div className="hint" style={{ marginBottom: 14 }}>
        Requires the server to have an AI API key configured (VOLTPHISH_AI_API_KEY). The draft
        replaces the current subject and body — you can edit before saving.
      </div>
      <div className="btn-row" style={{ justifyContent: "flex-end" }}>
        <button type="button" className="btn" onClick={onClose} disabled={busy}>
          Cancel
        </button>
        <button type="button" className="btn primary" onClick={generate} disabled={busy || scenario.trim().length < 4}>
          {busy ? "Generating…" : "Generate draft"}
        </button>
      </div>
    </Modal>
  );
}

function IcsModal({ onAdd, onClose }: { onAdd: (ics: string, filename: string) => Promise<void>; onClose: () => void }) {
  const [title, setTitle] = useState("Mandatory security briefing — action required");
  const [orgName, setOrgName] = useState("IT Service Desk");
  const [orgEmail, setOrgEmail] = useState("it-support@example.com");
  const [when, setWhen] = useState("");
  const [duration, setDuration] = useState(30);
  const [note, setNote] = useState("Please review your account settings before the meeting.");
  const [busy, setBusy] = useState(false);

  const esc = (s: string) => s.replace(/[\\;,]/g, (c) => "\\" + c).replace(/\r?\n/g, "\\n");
  const fmt = (d: Date) => d.toISOString().replace(/[-:]/g, "").split(".")[0] + "Z";

  const build = () => {
    const start = when ? new Date(when) : new Date(Date.now() + 24 * 3600 * 1000);
    const end = new Date(start.getTime() + duration * 60000);
    const uid = `${start.getTime()}-${Math.floor(Math.random() * 1e6)}@voltphish`;
    return [
      "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//VoltPhish//Invite//EN", "METHOD:REQUEST",
      "BEGIN:VEVENT",
      `UID:${uid}`,
      `DTSTAMP:${fmt(new Date())}`,
      `DTSTART:${fmt(start)}`,
      `DTEND:${fmt(end)}`,
      `SUMMARY:${esc(title)}`,
      `ORGANIZER;CN=${esc(orgName)}:mailto:${orgEmail}`,
      "LOCATION:{{.URL}}",
      `DESCRIPTION:${esc(note)}\\n\\nJoin here: {{.URL}}`,
      "STATUS:CONFIRMED", "SEQUENCE:0",
      "BEGIN:VALARM", "TRIGGER:-PT10M", "ACTION:DISPLAY", "DESCRIPTION:Reminder", "END:VALARM",
      "END:VEVENT", "END:VCALENDAR",
    ].join("\r\n");
  };

  const add = async () => {
    setBusy(true);
    await onAdd(build(), "invite.ics");
    setBusy(false);
  };

  return (
    <Modal title="📅 Add calendar invite (.ics)" onClose={onClose}>
      <p className="hint" style={{ marginBottom: 14 }}>
        Attaches a meeting invite whose link is <span className="mono">{"{{.URL}}"}</span> — rendered to each
        recipient's tracking link. Opening/accepting the invite and clicking through is tracked as a click.
      </p>
      <div className="field">
        <label>Event title</label>
        <input value={title} onChange={(e) => setTitle(e.target.value)} />
      </div>
      <div className="row2">
        <div className="field">
          <label>Organizer name</label>
          <input value={orgName} onChange={(e) => setOrgName(e.target.value)} />
        </div>
        <div className="field">
          <label>Organizer email</label>
          <input type="email" value={orgEmail} onChange={(e) => setOrgEmail(e.target.value)} />
        </div>
      </div>
      <div className="row2">
        <div className="field">
          <label>Start <span className="hint">(optional — default tomorrow)</span></label>
          <input type="datetime-local" value={when} onChange={(e) => setWhen(e.target.value)} />
        </div>
        <div className="field">
          <label>Duration (min)</label>
          <input type="number" min={5} value={duration} onChange={(e) => setDuration(Number(e.target.value))} />
        </div>
      </div>
      <div className="field">
        <label>Note</label>
        <input value={note} onChange={(e) => setNote(e.target.value)} />
      </div>
      <div className="btn-row" style={{ justifyContent: "flex-end" }}>
        <button type="button" className="btn" onClick={onClose} disabled={busy}>Cancel</button>
        <button type="button" className="btn primary" onClick={add} disabled={busy}>
          {busy ? "Attaching…" : "Attach invite"}
        </button>
      </div>
    </Modal>
  );
}
