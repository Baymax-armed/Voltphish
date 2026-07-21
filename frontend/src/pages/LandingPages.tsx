import { useEffect, useState } from "react";
import { api, ApiError } from "../api";
import type { PageSummary, LandingPage } from "../types";
import { BulkBar, Empty, FormSkeleton, ListSkeleton, Modal, RowMenu, fmtDate, useSelection } from "../components/ui";
import { confirmDialog } from "../components/dialog";
import { useToast } from "../components/Toast";
import HtmlEditor from "../components/HtmlEditor";
import { GALLERY_PAGES, type GalleryPage } from "../gallery";

const SAMPLE = `<!doctype html>
<html><head><meta charset="utf-8"><title>Sign in</title></head>
<body style="font-family:system-ui;max-width:22rem;margin:4rem auto">
  <h1 style="font-size:1.2rem">Hi {{.FirstName}}, sign in to continue</h1>
  <form method="post">
    <p><label>Email<br><input name="username" type="email" style="width:100%"></label></p>
    <p><label>Password<br><input name="password" type="password" style="width:100%"></label></p>
    <button type="submit">Sign in</button>
  </form>
</body></html>`;

export default function LandingPages() {
  const { notify } = useToast();
  const [items, setItems] = useState<PageSummary[] | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [creating, setCreating] = useState(false);
  const [gallery, setGallery] = useState(false);
  const { sel, toggle, clear, allToggle } = useSelection();

  const load = () => api.listPages().then(setItems);
  useEffect(() => {
    load();
  }, []);

  const bulkDelete = async () => {
    if (!(await confirmDialog({ title: "Delete landing pages", message: `Delete ${sel.size} landing page${sel.size > 1 ? "s" : ""}?`, confirmLabel: "Delete", danger: true }))) return;
    let ok = 0;
    let fail = 0;
    for (const id of sel) {
      try {
        await api.deletePage(id);
        ok++;
      } catch {
        fail++;
      }
    }
    notify(fail ? `Deleted ${ok}; ${fail} still used by a campaign.` : `Deleted ${ok} page${ok > 1 ? "s" : ""}.`, fail ? "error" : "ok");
    clear();
    load();
  };

  const useFromGallery = async (g: GalleryPage) => {
    try {
      const existing = new Set((items ?? []).map((p) => p.name));
      let name = g.name;
      let n = 2;
      while (existing.has(name)) name = `${g.name} ${n++}`;
      await api.createPage({ name, html: g.html, redirect_url: null });
      notify(`Added "${name}" — edit to customize`);
      setGallery(false);
      load();
    } catch (e) {
      notify(e instanceof ApiError ? e.message : "Failed", "error");
    }
  };

  const remove = async (p: PageSummary) => {
    if (!(await confirmDialog({ title: "Delete landing page", message: `Delete "${p.name}"?`, confirmLabel: "Delete", danger: true }))) return;
    try {
      await api.deletePage(p.id);
      notify("Landing page deleted");
      load();
    } catch (e) {
      notify(e instanceof ApiError ? e.message : "Delete failed", "error");
    }
  };

  if (!items) return <ListSkeleton cols={3} />;
  const ids = items.map((p) => p.id);
  const allChecked = ids.length > 0 && ids.every((id) => sel.has(id));

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Landing Pages</h1>
          <div className="page-sub">
            The page a recipient sees after clicking. Any form is captured automatically —
            passwords are never stored.
          </div>
        </div>
        <div className="btn-row">
          <button className="btn" onClick={() => setGallery(true)}>
            📚 Gallery
          </button>
          <button className="btn primary" onClick={() => setCreating(true)}>
            + New landing page
          </button>
        </div>
      </div>

      {gallery && (
        <Modal title="Landing-page gallery — one click to add" onClose={() => setGallery(false)} wide>
          <div className="grid cols-2" style={{ gap: 12 }}>
            {GALLERY_PAGES.map((g) => (
              <div className="card hover" key={g.name} style={{ cursor: "pointer" }} onClick={() => useFromGallery(g)}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                  <strong>{g.name}</strong>
                  <span className="badge scheduled">{g.category}</span>
                </div>
                <div style={{ height: 150, overflow: "hidden", border: "1px solid var(--border)", borderRadius: 8, pointerEvents: "none", background: "#fff" }}>
                  <iframe title={g.name} sandbox="" style={{ width: "100%", height: 280, border: 0, display: "block" }} srcDoc={"<style>html{zoom:0.6}body{margin:0}</style>" + g.html} />
                </div>
              </div>
            ))}
          </div>
        </Modal>
      )}

      <BulkBar count={sel.size} noun="page" onDelete={bulkDelete} onClear={clear} />

      {items.length === 0 ? (
        <div className="card">
          <Empty>No landing pages yet. Campaigns without one use a built-in awareness page.</Empty>
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
                <th>Redirect after submit</th>
                <th>Modified</th>
                <th className="actions-col"></th>
              </tr>
            </thead>
            <tbody>
              {items.map((p) => (
                <tr key={p.id} className={sel.has(p.id) ? "selected" : ""}>
                  <td className="check-col">
                    <input type="checkbox" aria-label={`Select ${p.name}`} checked={sel.has(p.id)} onChange={() => toggle(p.id)} />
                  </td>
                  <td>
                    <strong>{p.name}</strong>
                  </td>
                  <td className="mono">{p.redirect_url || "—"}</td>
                  <td>{fmtDate(p.modified_at)}</td>
                  <td className="actions-col">
                    <RowMenu
                      items={[
                        { label: "Edit", icon: "✎", onClick: () => setEditingId(p.id) },
                        { label: "Delete", icon: "🗑", danger: true, onClick: () => remove(p) },
                      ]}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {(creating || editingId !== null) && (
        <PageForm
          pageId={editingId}
          onClose={() => {
            setCreating(false);
            setEditingId(null);
          }}
          onSaved={() => {
            setCreating(false);
            setEditingId(null);
            load();
          }}
        />
      )}
    </>
  );
}

function PageForm({
  pageId,
  onClose,
  onSaved,
}: {
  pageId: number | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const { notify } = useToast();
  const [name, setName] = useState("");
  const [html, setHtml] = useState(SAMPLE);
  const [redirect, setRedirect] = useState("");
  const [busy, setBusy] = useState(false);
  const [loaded, setLoaded] = useState(pageId === null);
  const [importUrl, setImportUrl] = useState("");
  const [importing, setImporting] = useState(false);
  const [aiOpen, setAiOpen] = useState(false);

  const doImportSite = async () => {
    if (!importUrl.trim()) return;
    setImporting(true);
    try {
      const res = await api.importSite(importUrl);
      setHtml(res.html);
      notify("Site imported — review, then save");
    } catch (e) {
      notify(e instanceof ApiError ? e.message : "Import failed", "error");
    } finally {
      setImporting(false);
    }
  };

  useEffect(() => {
    if (pageId !== null) {
      api.getPage(pageId).then((p: LandingPage) => {
        setName(p.name);
        setHtml(p.html);
        setRedirect(p.redirect_url ?? "");
        setLoaded(true);
      });
    }
  }, [pageId]);

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    const payload = { name, html, redirect_url: redirect || null };
    try {
      if (pageId !== null) await api.updatePage(pageId, payload);
      else await api.createPage(payload);
      notify("Landing page saved");
      onSaved();
    } catch (e) {
      notify(e instanceof ApiError ? e.message : "Save failed", "error");
      setBusy(false);
    }
  };

  if (!loaded)
    return (
      <Modal title="Loading…" onClose={onClose}>
        <FormSkeleton fields={4} />
      </Modal>
    );

  return (
    <Modal title={pageId !== null ? "Edit landing page" : "New landing page"} onClose={onClose} wide>
      <form onSubmit={save}>
        <div className="row2">
          <div className="field">
            <label>Name</label>
            <input value={name} onChange={(e) => setName(e.target.value)} required />
          </div>
          <div className="field">
            <label>Redirect after submit <span className="hint">(optional teaching page)</span></label>
            <input
              value={redirect}
              onChange={(e) => setRedirect(e.target.value)}
              placeholder="https://intranet.example.com/awareness"
            />
          </div>
        </div>
        <div className="field">
          <label>Start from <span className="hint">import a real site, or let AI draft one</span></label>
          <div style={{ display: "flex", gap: 8 }}>
            <input
              value={importUrl}
              onChange={(e) => setImportUrl(e.target.value)}
              placeholder="https://login.example.com"
            />
            <button type="button" className="btn" onClick={doImportSite} disabled={importing || !importUrl.trim()}>
              {importing ? "Importing…" : "⭱ Import Site"}
            </button>
            <button type="button" className="btn primary" onClick={() => setAiOpen(true)} style={{ whiteSpace: "nowrap" }}>
              ✨ Generate with AI
            </button>
          </div>
        </div>
        {aiOpen && (
          <AiPageModal
            onApply={(r) => {
              setHtml(r.html);
              if (!name.trim()) setName(r.name);
              setAiOpen(false);
              notify("AI draft applied — review and save");
            }}
            onClose={() => setAiOpen(false)}
          />
        )}
        <div className="field">
          <label>
            Page content <span className="hint">design visually or edit HTML — any form auto-posts to the tracker</span>
          </label>
          <HtmlEditor
            value={html}
            onChange={setHtml}
            height={360}
            variables={[
              { token: "{{.FirstName}}", label: "First name" },
              { token: "{{.LastName}}", label: "Last name" },
              { token: "{{.Email}}", label: "Email" },
              { token: "{{.Position}}", label: "Position" },
            ]}
          />
        </div>
        <div className="btn-row" style={{ justifyContent: "flex-end" }}>
          <button type="button" className="btn" onClick={onClose}>
            Cancel
          </button>
          <button className="btn primary" disabled={busy}>
            {busy ? "Saving…" : "Save landing page"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

function AiPageModal({
  onApply,
  onClose,
}: {
  onApply: (r: { name: string; html: string }) => void;
  onClose: () => void;
}) {
  const { notify } = useToast();
  const [scenario, setScenario] = useState("");
  const [busy, setBusy] = useState(false);

  const EXAMPLES = [
    "Microsoft 365 sign-in page to verify your account",
    "Company VPN portal login",
    "HR payroll portal — confirm your bank details",
    "Password reset form after a 'security alert'",
  ];

  const generate = async () => {
    setBusy(true);
    try {
      const r = await api.aiGeneratePage(scenario);
      onApply(r);
    } catch (e) {
      notify(e instanceof ApiError ? e.message : "AI generation failed", "error");
      setBusy(false);
    }
  };

  return (
    <Modal title="✨ Generate landing page with AI" onClose={onClose}>
      <div className="field">
        <label>
          Describe the page <span className="hint">the AI builds a self-contained HTML page with a capturing form</span>
        </label>
        <textarea
          value={scenario}
          onChange={(e) => setScenario(e.target.value)}
          rows={3}
          placeholder="e.g. Microsoft 365 sign-in page to re-verify your mailbox"
          autoFocus
        />
      </div>
      <div className="field">
        <label>Try an example</label>
        <div className="btn-row" style={{ flexWrap: "wrap", gap: 6 }}>
          {EXAMPLES.map((ex) => (
            <button key={ex} type="button" className="btn sm" onClick={() => setScenario(ex)} title={ex}>
              {ex.length > 32 ? ex.slice(0, 32) + "…" : ex}
            </button>
          ))}
        </div>
      </div>
      <div className="hint" style={{ marginBottom: 14 }}>
        Requires an AI key under <strong>Settings → AI</strong>. The draft replaces the current page content — edit before saving.
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
