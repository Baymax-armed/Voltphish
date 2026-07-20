import { useEffect, useState } from "react";
import { api, ApiError } from "../api";
import type { AdminUser, Role } from "../types";
import { Badge, BulkBar, Empty, ListSkeleton, Modal, RowMenu, fmtDate, useSelection } from "../components/ui";
import { confirmDialog, promptDialog } from "../components/dialog";
import { useToast } from "../components/Toast";
import { useAuth } from "../auth";

export default function Users() {
  const { notify } = useToast();
  const { user: me } = useAuth();
  const [items, setItems] = useState<AdminUser[] | null>(null);
  const [creating, setCreating] = useState(false);
  const { sel, toggle, clear, allToggle } = useSelection();

  const load = () => api.listUsers().then(setItems);
  useEffect(() => {
    load();
  }, []);

  const bulkDelete = async () => {
    if (!(await confirmDialog({ title: "Delete users", message: `Delete ${sel.size} user${sel.size > 1 ? "s" : ""}?`, confirmLabel: "Delete", danger: true }))) return;
    let ok = 0;
    let fail = 0;
    for (const id of sel) {
      try {
        await api.deleteUser(id);
        ok++;
      } catch {
        fail++;
      }
    }
    notify(fail ? `Deleted ${ok}; ${fail} failed.` : `Deleted ${ok} user${ok > 1 ? "s" : ""}.`, fail ? "error" : "ok");
    clear();
    load();
  };

  const act = async (fn: () => Promise<unknown>, ok: string) => {
    try {
      await fn();
      notify(ok);
      load();
    } catch (e) {
      notify(e instanceof ApiError ? e.message : "Failed", "error");
    }
  };

  const setRole = (u: AdminUser, role: Role) => act(() => api.updateUser(u.id, { role }), "Role updated");
  const toggleActive = (u: AdminUser) =>
    act(() => api.updateUser(u.id, { is_active: !u.is_active }), u.is_active ? "User disabled" : "User enabled");
  const remove = async (u: AdminUser) => {
    if (!(await confirmDialog({ title: "Delete user", message: `Delete ${u.email}?`, confirmLabel: "Delete", danger: true }))) return;
    act(() => api.deleteUser(u.id), "User deleted");
  };
  const reset = async (u: AdminUser) => {
    const pw = await promptDialog({
      title: "Reset password",
      message: `Set a new password for ${u.email}.`,
      placeholder: "New password (min 12 characters)",
      password: true,
      minLength: 12,
      confirmLabel: "Reset password",
    });
    if (!pw) return;
    act(() => api.resetUserPassword(u.id, pw), "Password reset");
  };

  if (!items) return <ListSkeleton cols={4} />;
  const ids = items.filter((u) => u.id !== me?.id).map((u) => u.id);
  const allChecked = ids.length > 0 && ids.every((id) => sel.has(id));

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Users</h1>
          <div className="page-sub">Manage who can operate VoltPhish</div>
        </div>
        <button className="btn primary" onClick={() => setCreating(true)}>
          + New user
        </button>
      </div>

      <BulkBar count={sel.size} noun="user" onDelete={bulkDelete} onClear={clear} />

      {items.length === 0 ? (
        <div className="card">
          <Empty>No users.</Empty>
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
                <th>Email</th>
                <th>Role</th>
                <th>Status</th>
                <th>Created</th>
                <th className="actions-col"></th>
              </tr>
            </thead>
            <tbody>
              {items.map((u) => (
                <tr key={u.id} className={sel.has(u.id) ? "selected" : ""}>
                  <td className="check-col">
                    <input
                      type="checkbox"
                      aria-label={`Select ${u.email}`}
                      disabled={u.id === me?.id}
                      checked={sel.has(u.id)}
                      onChange={() => toggle(u.id)}
                    />
                  </td>
                  <td>
                    <strong>{u.email}</strong>
                    {u.id === me?.id && <span className="hint"> (you)</span>}
                  </td>
                  <td>
                    <select
                      value={u.role}
                      disabled={u.id === me?.id}
                      onChange={(e) => setRole(u, e.target.value as Role)}
                    >
                      <option value="admin">admin</option>
                      <option value="operator">operator</option>
                    </select>
                  </td>
                  <td>
                    <Badge status={u.is_active ? "completed" : "error"} />
                  </td>
                  <td>{fmtDate(u.created_at)}</td>
                  <td className="actions-col">
                    <RowMenu
                      items={[
                        { label: "Reset password", icon: "🔑", onClick: () => reset(u) },
                        ...(u.id === me?.id
                          ? []
                          : [
                              { label: u.is_active ? "Disable" : "Enable", icon: u.is_active ? "🚫" : "✓", onClick: () => toggleActive(u) },
                              { label: "Delete", icon: "🗑", danger: true, onClick: () => remove(u) },
                            ]),
                      ]}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {creating && (
        <CreateUser
          onClose={() => setCreating(false)}
          onSaved={() => {
            setCreating(false);
            load();
          }}
        />
      )}
    </>
  );
}

function CreateUser({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) {
  const { notify } = useToast();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<Role>("operator");
  const [busy, setBusy] = useState(false);

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      await api.createUser({ email, password, role });
      notify("User created");
      onSaved();
    } catch (e) {
      notify(e instanceof ApiError ? e.message : "Create failed", "error");
      setBusy(false);
    }
  };

  return (
    <Modal title="New user" onClose={onClose}>
      <form onSubmit={save}>
        <div className="field">
          <label>Email</label>
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </div>
        <div className="field">
          <label>Password <span className="hint">(min 12 characters)</span></label>
          <input
            type="password"
            value={password}
            autoComplete="new-password"
            minLength={12}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </div>
        <div className="field">
          <label>Role</label>
          <select value={role} onChange={(e) => setRole(e.target.value as Role)}>
            <option value="operator">operator</option>
            <option value="admin">admin</option>
          </select>
        </div>
        <div className="btn-row" style={{ justifyContent: "flex-end" }}>
          <button type="button" className="btn" onClick={onClose}>
            Cancel
          </button>
          <button className="btn primary" disabled={busy}>
            {busy ? "Creating…" : "Create user"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
