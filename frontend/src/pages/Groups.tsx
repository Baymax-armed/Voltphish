import { useEffect, useState } from "react";
import { api, ApiError } from "../api";
import type { GroupSummary, Target } from "../types";
import { BulkBar, Empty, FormSkeleton, ListSkeleton, Modal, RowMenu, fmtDate, useSelection } from "../components/ui";
import { confirmDialog } from "../components/dialog";
import { useToast } from "../components/Toast";

export default function Groups() {
  const { notify } = useToast();
  const [items, setItems] = useState<GroupSummary[] | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [creating, setCreating] = useState(false);
  const { sel, toggle, clear, allToggle } = useSelection();

  const load = () => api.listGroups().then(setItems);
  useEffect(() => {
    load();
  }, []);

  const remove = async (g: GroupSummary) => {
    if (!(await confirmDialog({ title: "Delete group", message: `Delete "${g.name}"?`, confirmLabel: "Delete", danger: true }))) return;
    try {
      await api.deleteGroup(g.id);
      notify("Group deleted");
      load();
    } catch (e) {
      notify(e instanceof ApiError ? e.message : "Delete failed", "error");
    }
  };

  const bulkDelete = async () => {
    if (!(await confirmDialog({ title: "Delete groups", message: `Delete ${sel.size} group${sel.size > 1 ? "s" : ""}?`, confirmLabel: "Delete", danger: true }))) return;
    let ok = 0;
    let fail = 0;
    for (const id of sel) {
      try {
        await api.deleteGroup(id);
        ok++;
      } catch {
        fail++;
      }
    }
    notify(fail ? `Deleted ${ok}; ${fail} still used by a campaign.` : `Deleted ${ok} group${ok > 1 ? "s" : ""}.`, fail ? "error" : "ok");
    clear();
    load();
  };

  if (!items) return <ListSkeleton cols={3} />;
  const ids = items.map((g) => g.id);
  const allChecked = ids.length > 0 && ids.every((id) => sel.has(id));

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Groups &amp; Targets</h1>
          <div className="page-sub">People to include in a campaign</div>
        </div>
        <button className="btn primary" onClick={() => setCreating(true)}>
          + New group
        </button>
      </div>

      <BulkBar count={sel.size} noun="group" onDelete={bulkDelete} onClear={clear} />

      {items.length === 0 ? (
        <div className="card">
          <Empty>No groups yet.</Empty>
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
                <th>Targets</th>
                <th>Modified</th>
                <th className="actions-col"></th>
              </tr>
            </thead>
            <tbody>
              {items.map((g) => (
                <tr key={g.id} className={sel.has(g.id) ? "selected" : ""}>
                  <td className="check-col">
                    <input type="checkbox" aria-label={`Select ${g.name}`} checked={sel.has(g.id)} onChange={() => toggle(g.id)} />
                  </td>
                  <td>
                    <strong>{g.name}</strong>
                  </td>
                  <td>{g.target_count}</td>
                  <td>{fmtDate(g.modified_at)}</td>
                  <td className="actions-col">
                    <RowMenu
                      items={[
                        { label: "Edit", icon: "✎", onClick: () => setEditingId(g.id) },
                        { label: "Delete", icon: "🗑", danger: true, onClick: () => remove(g) },
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
        <GroupForm
          groupId={editingId}
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

// Split a single CSV/TSV line, honoring quoted fields ("a, b", ""escaped"").
function splitCsvLine(line: string): string[] {
  const out: string[] = [];
  let cur = "";
  let q = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (q) {
      if (ch === '"') {
        if (line[i + 1] === '"') {
          cur += '"';
          i++;
        } else q = false;
      } else cur += ch;
    } else if (ch === '"') {
      q = true;
    } else if (ch === "," || ch === "\t") {
      out.push(cur);
      cur = "";
    } else cur += ch;
  }
  out.push(cur);
  return out.map((s) => s.trim());
}

// Parse CSV/TSV text into targets. Supports a Gophish-style header row (First
// Name, Last Name, Email, Position, Phone — any order) OR headerless rows where
// the email is auto-detected by the "@".
function parseCsv(text: string): Target[] {
  const lines = text.split(/\r?\n/).map((l) => l.trim()).filter(Boolean);
  if (!lines.length) return [];

  const firstCols = splitCsvLine(lines[0]).map((c) => c.toLowerCase());
  const hasHeader = firstCols.some((c) => c.includes("email")) && !firstCols.some((c) => c.includes("@"));

  const idx = { email: -1, first: -1, last: -1, position: -1, phone: -1 };
  let dataLines = lines;
  if (hasHeader) {
    firstCols.forEach((c, i) => {
      if (c.includes("email")) idx.email = i;
      else if (c.includes("first")) idx.first = i;
      else if (c.includes("last")) idx.last = i;
      else if (c.includes("position") || c.includes("title") || c.includes("department") || c.includes("role")) idx.position = i;
      else if (c.includes("phone") || c.includes("mobile")) idx.phone = i;
    });
    dataLines = lines.slice(1);
  }

  const out: Target[] = [];
  for (const line of dataLines) {
    const cols = splitCsvLine(line);
    let email: string | undefined;
    let first: string | null = null;
    let last: string | null = null;
    let position: string | null = null;
    let phone: string | null = null;
    if (hasHeader && idx.email >= 0) {
      email = cols[idx.email];
      first = idx.first >= 0 ? cols[idx.first] || null : null;
      last = idx.last >= 0 ? cols[idx.last] || null : null;
      position = idx.position >= 0 ? cols[idx.position] || null : null;
      phone = idx.phone >= 0 ? cols[idx.phone] || null : null;
    } else {
      const emailIdx = cols.findIndex((c) => c.includes("@"));
      if (emailIdx < 0) continue;
      email = cols[emailIdx];
      const rest = cols.filter((_, i) => i !== emailIdx);
      first = rest[0] || null;
      last = rest[1] || null;
      position = rest[2] || null;
      phone = rest.find((c) => /^[+\d][\d\s()-]{6,}$/.test(c)) || null;
    }
    if (!email || !email.includes("@")) continue;
    out.push({ email, first_name: first, last_name: last, position, phone });
  }
  return out;
}

function GroupForm({
  groupId,
  onClose,
  onSaved,
}: {
  groupId: number | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const { notify } = useToast();
  const [name, setName] = useState("");
  const [targets, setTargets] = useState<Target[]>([]);
  const [bulk, setBulk] = useState("");
  const [busy, setBusy] = useState(false);
  const [loaded, setLoaded] = useState(groupId === null);

  useEffect(() => {
    if (groupId !== null) {
      api.getGroup(groupId).then((g) => {
        setName(g.name);
        setTargets(g.targets);
        setLoaded(true);
      });
    }
  }, [groupId]);

  const mergeTargets = (parsed: Target[], source: string) => {
    if (!parsed.length) {
      notify("No valid rows found — need an email in each row.", "error");
      return;
    }
    const seen = new Set(targets.map((t) => t.email.toLowerCase()));
    const merged = [...targets];
    for (const t of parsed) if (!seen.has(t.email.toLowerCase())) {
      merged.push(t);
      seen.add(t.email.toLowerCase());
    }
    const added = merged.length - targets.length;
    setTargets(merged);
    notify(added ? `Imported ${added} target${added > 1 ? "s" : ""} from ${source}.` : "No new targets (all were duplicates).");
  };

  const addBulk = () => {
    mergeTargets(parseCsv(bulk), "pasted rows");
    setBulk("");
  };

  const onFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    if (file.size > 5 * 1024 * 1024) {
      notify("File exceeds 5 MB.", "error");
      return;
    }
    try {
      const text = await file.text();
      mergeTargets(parseCsv(text), file.name);
    } catch {
      notify("Couldn't read that file.", "error");
    }
  };

  const downloadTemplate = () => {
    const csv = "First Name,Last Name,Email,Position,Phone\nAlice,Ng,alice@example.com,Finance,+15551112222\nBob,Lee,bob@example.com,Sales,\n";
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = "voltphish-targets-template.csv";
    a.click();
    URL.revokeObjectURL(url);
  };

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!targets.length) {
      notify("Add at least one target", "error");
      return;
    }
    setBusy(true);
    const payload = { name, targets: targets.map((t) => ({ ...t })) };
    try {
      if (groupId !== null) await api.updateGroup(groupId, payload);
      else await api.createGroup(payload);
      notify("Group saved");
      onSaved();
    } catch (e) {
      notify(e instanceof ApiError ? e.message : "Save failed", "error");
      setBusy(false);
    }
  };

  if (!loaded) return <Modal title="Loading…" onClose={onClose}><FormSkeleton fields={4} /></Modal>;

  return (
    <Modal title={groupId !== null ? "Edit group" : "New group"} onClose={onClose} wide>
      <form onSubmit={save}>
        <div className="field">
          <label>Group name</label>
          <input value={name} onChange={(e) => setName(e.target.value)} required />
        </div>

        <div className="field">
          <label>
            Import targets{" "}
            <span className="hint">upload a CSV, or paste rows below</span>
          </label>
          <div className="btn-row" style={{ marginBottom: 10 }}>
            <label className="btn sm" style={{ cursor: "pointer" }}>
              📄 Upload CSV
              <input type="file" accept=".csv,text/csv,.tsv,text/plain" onChange={onFile} style={{ display: "none" }} />
            </label>
            <button type="button" className="btn sm" onClick={downloadTemplate}>
              ⭳ Download template
            </button>
          </div>
          <textarea
            value={bulk}
            onChange={(e) => setBulk(e.target.value)}
            placeholder={"Paste rows — with or without a header. Examples:\nFirst Name,Last Name,Email,Position,Phone\nAlice,Ng,alice@example.com,Finance,+15551112222\n\n…or headerless: alice@example.com, Alice, Ng, Finance"}
            rows={4}
          />
          <div>
            <button type="button" className="btn sm" onClick={addBulk}>
              Add pasted rows
            </button>
          </div>
        </div>

        <div className="field">
          <label>Targets ({targets.length})</label>
          {targets.length > 0 && (
            <div className="table-wrap" style={{ maxHeight: 240, overflow: "auto" }}>
              <table>
                <thead>
                  <tr>
                    <th>Email</th>
                    <th>Phone</th>
                    <th>First</th>
                    <th>Last</th>
                    <th>Position</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {targets.map((t, i) => (
                    <tr key={i}>
                      <td className="mono">{t.email}</td>
                      <td className="mono">{t.phone || "—"}</td>
                      <td>{t.first_name || "—"}</td>
                      <td>{t.last_name || "—"}</td>
                      <td>{t.position || "—"}</td>
                      <td>
                        <button
                          type="button"
                          className="btn sm danger"
                          onClick={() => setTargets(targets.filter((_, j) => j !== i))}
                        >
                          ✕
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className="btn-row" style={{ justifyContent: "flex-end" }}>
          <button type="button" className="btn" onClick={onClose}>
            Cancel
          </button>
          <button className="btn primary" disabled={busy}>
            {busy ? "Saving…" : "Save group"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
