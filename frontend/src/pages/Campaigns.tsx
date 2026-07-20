import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, ApiError } from "../api";
import type { Campaign, GroupSummary, PageSummary, Profile, SmsProfile, Template } from "../types";
import { Badge, BulkBar, Empty, FormSkeleton, ListSkeleton, Modal, RowMenu, fmtDate, useSelection } from "../components/ui";
import { confirmDialog } from "../components/dialog";
import { useToast } from "../components/Toast";

export default function Campaigns() {
  const { notify } = useToast();
  const nav = useNavigate();
  const [items, setItems] = useState<Campaign[] | null>(null);
  const [creating, setCreating] = useState(false);
  const [q, setQ] = useState("");
  const { sel, toggle, clear, allToggle } = useSelection();

  const load = () => api.listCampaigns().then(setItems);
  useEffect(() => {
    load();
  }, []);

  const bulkDelete = async () => {
    if (!(await confirmDialog({ title: "Delete campaigns", message: `Delete ${sel.size} campaign${sel.size > 1 ? "s" : ""} and all their results? This can't be undone.`, confirmLabel: "Delete", danger: true }))) return;
    let ok = 0;
    let fail = 0;
    for (const id of sel) {
      try {
        await api.deleteCampaign(id);
        ok++;
      } catch {
        fail++;
      }
    }
    notify(fail ? `Deleted ${ok}; ${fail} couldn't be deleted.` : `Deleted ${ok} campaign${ok > 1 ? "s" : ""}.`, fail ? "error" : "ok");
    clear();
    load();
  };

  const remove = async (c: Campaign) => {
    if (!(await confirmDialog({ title: "Delete campaign", message: `Delete "${c.name}" and all its results?`, confirmLabel: "Delete", danger: true }))) return;
    try {
      await api.deleteCampaign(c.id);
      notify("Campaign deleted");
      load();
    } catch (e) {
      notify(e instanceof ApiError ? e.message : "Delete failed", "error");
    }
  };

  const clone = async (c: Campaign) => {
    try {
      await api.createCampaign({
        name: `${c.name} (copy)`, channel: c.channel, template_id: c.template_id,
        profile_id: c.profile_id, sms_profile_id: c.sms_profile_id, group_id: c.group_id,
        page_id: c.page_id, phish_url: c.phish_url, redirect_url: c.redirect_url,
      });
      notify("Campaign cloned as draft");
      load();
    } catch (e) {
      notify(e instanceof ApiError ? e.message : "Clone failed", "error");
    }
  };

  const filtered = items?.filter((c) => c.name.toLowerCase().includes(q.toLowerCase())) ?? [];
  const ids = filtered.map((c) => c.id);
  const allChecked = ids.length > 0 && ids.every((id) => sel.has(id));

  if (!items) return <ListSkeleton cols={4} />;

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Campaigns</h1>
          <div className="page-sub">Launch and track phishing simulations</div>
        </div>
        <button className="btn primary" onClick={() => setCreating(true)}>
          + New campaign
        </button>
      </div>

      {items.length > 0 && (
        <input className="search-box" placeholder="Search campaigns…" value={q} onChange={(e) => setQ(e.target.value)} />
      )}

      <BulkBar count={sel.size} noun="campaign" onDelete={bulkDelete} onClear={clear} />

      {items.length === 0 ? (
        <div className="card">
          <Empty>No campaigns yet. Create one to begin.</Empty>
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
                <th>Channel</th>
                <th>Status</th>
                <th>Created</th>
                <th className="actions-col"></th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((c) => (
                <tr key={c.id} className={sel.has(c.id) ? "selected" : ""}>
                  <td className="check-col">
                    <input type="checkbox" aria-label={`Select ${c.name}`} checked={sel.has(c.id)} onChange={() => toggle(c.id)} />
                  </td>
                  <td>
                    <Link to={`/campaigns/${c.id}`}>
                      <strong>{c.name}</strong>
                    </Link>
                  </td>
                  <td>{c.channel === "sms" ? "📱 SMS" : "📧 Email"}</td>
                  <td>
                    <Badge status={c.status} />
                  </td>
                  <td>{fmtDate(c.created_at)}</td>
                  <td className="actions-col">
                    <RowMenu
                      items={[
                        { label: "View", icon: "→", onClick: () => nav(`/campaigns/${c.id}`) },
                        { label: "Clone as draft", icon: "⧉", onClick: () => clone(c) },
                        { label: "Delete", icon: "🗑", danger: true, onClick: () => remove(c) },
                      ]}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {creating && <CampaignForm onClose={() => setCreating(false)} />}
    </>
  );
}

function CampaignForm({ onClose }: { onClose: () => void }) {
  const { notify } = useToast();
  const nav = useNavigate();
  const [templates, setTemplates] = useState<Template[]>([]);
  const [groups, setGroups] = useState<GroupSummary[]>([]);
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [pages, setPages] = useState<PageSummary[]>([]);
  const [smsProfiles, setSmsProfiles] = useState<SmsProfile[]>([]);
  const [ready, setReady] = useState(false);
  const [busy, setBusy] = useState(false);
  const [launch, setLaunch] = useState(true);
  const [channel] = useState<"email" | "sms">("email");

  const [f, setF] = useState({
    name: "",
    template_id: 0,
    profile_id: 0,
    sms_profile_id: 0,
    group_id: 0,
    page_id: 0, // 0 => built-in awareness page
    phish_url: window.location.origin,
    redirect_url: "",
    launch_at: "", // datetime-local; empty => launch now/manual
    send_by_at: "",
  });
  const set = (k: string, v: unknown) => setF((p) => ({ ...p, [k]: v }));
  const channelTemplates = templates.filter((t) => t.channel === channel);

  useEffect(() => {
    Promise.all([
      api.listTemplates(), api.listGroups(), api.listProfiles(), api.listPages(), api.listSmsProfiles(),
    ]).then(([t, g, p, pg, sp]) => {
      setTemplates(t);
      setGroups(g);
      setProfiles(p);
      setPages(pg);
      setSmsProfiles(sp);
      setF((prev) => ({
        ...prev,
        template_id: t[0]?.id ?? 0,
        group_id: g[0]?.id ?? 0,
        profile_id: p[0]?.id ?? 0,
        sms_profile_id: sp[0]?.id ?? 0,
      }));
      setReady(true);
    });
  }, []);

  // Keep the selected template valid for the chosen channel.
  useEffect(() => {
    if (channelTemplates.length && !channelTemplates.some((t) => t.id === f.template_id)) {
      set("template_id", channelTemplates[0].id);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [channel, templates]);

  const missing =
    ready &&
    (!groups.length ||
      (channel === "email" ? !templates.some((t) => t.channel === "email") || !profiles.length
        : !templates.some((t) => t.channel === "sms") || !smsProfiles.length));

  const scheduled = f.launch_at !== "";

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      const created = await api.createCampaign({
        name: f.name,
        channel,
        template_id: f.template_id,
        profile_id: channel === "email" ? f.profile_id : null,
        sms_profile_id: channel === "sms" ? f.sms_profile_id : null,
        group_id: f.group_id,
        page_id: channel === "email" ? f.page_id || null : null,
        phish_url: f.phish_url,
        redirect_url: f.redirect_url || null,
        launch_at: f.launch_at ? new Date(f.launch_at).toISOString() : null,
        send_by_at: f.send_by_at ? new Date(f.send_by_at).toISOString() : null,
      });
      if (scheduled) {
        notify("Campaign scheduled");
      } else if (launch) {
        await api.launchCampaign(created.id);
        notify("Campaign launched");
      } else {
        notify("Campaign saved as draft");
      }
      onClose();
      nav(`/campaigns/${created.id}`);
    } catch (e) {
      notify(e instanceof ApiError ? e.message : "Failed to create campaign", "error");
      setBusy(false);
    }
  };

  return (
    <Modal title="New campaign" onClose={onClose}>
      {!ready ? (
        <FormSkeleton fields={6} />
      ) : missing ? (
        <Empty>
          You need at least one template, group, and sending profile first.
          <div className="btn-row" style={{ justifyContent: "center", marginTop: 14 }}>
            <Link className="btn sm" to="/templates" onClick={onClose}>
              Templates
            </Link>
            <Link className="btn sm" to="/groups" onClick={onClose}>
              Groups
            </Link>
            <Link className="btn sm" to="/profiles" onClick={onClose}>
              Profiles
            </Link>
          </div>
        </Empty>
      ) : (
        <form onSubmit={submit}>
          <div className="field">
            <label>Campaign name</label>
            <input value={f.name} onChange={(e) => set("name", e.target.value)} required />
          </div>
          <div className="field">
            <label>{channel === "sms" ? "SMS template" : "Email template"}</label>
            <select value={f.template_id} onChange={(e) => set("template_id", Number(e.target.value))}>
              {channelTemplates.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                </option>
              ))}
            </select>
          </div>
          <div className="row2">
            <div className="field">
              <label>Target group {channel === "sms" && <span className="hint">(needs phone numbers)</span>}</label>
              <select value={f.group_id} onChange={(e) => set("group_id", Number(e.target.value))}>
                {groups.map((g) => (
                  <option key={g.id} value={g.id}>
                    {g.name} ({g.target_count})
                  </option>
                ))}
              </select>
            </div>
            {channel === "email" ? (
              <div className="field">
                <label>Sending profile</label>
                <select value={f.profile_id} onChange={(e) => set("profile_id", Number(e.target.value))}>
                  {profiles.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </select>
              </div>
            ) : (
              <div className="field">
                <label>SMS profile</label>
                <select value={f.sms_profile_id} onChange={(e) => set("sms_profile_id", Number(e.target.value))}>
                  {smsProfiles.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name} ({p.provider})
                    </option>
                  ))}
                </select>
              </div>
            )}
          </div>
          {channel === "email" && (
            <div className="field">
              <label>
                Landing page <span className="hint">what recipients see after clicking</span>
              </label>
              <select value={f.page_id} onChange={(e) => set("page_id", Number(e.target.value))}>
                <option value={0}>Built-in awareness page</option>
                {pages.map((pg) => (
                  <option key={pg.id} value={pg.id}>
                    {pg.name}
                  </option>
                ))}
              </select>
            </div>
          )}
          <div className="field">
            <label>
              Phishing URL <span className="hint">base URL recipients' links resolve to</span>
            </label>
            <input value={f.phish_url} onChange={(e) => set("phish_url", e.target.value)} required />
          </div>
          <div className="field">
            <label>
              Redirect URL <span className="hint">(optional) where a click ultimately lands — e.g. a teaching page</span>
            </label>
            <input
              value={f.redirect_url}
              onChange={(e) => set("redirect_url", e.target.value)}
              placeholder="https://intranet.example.com/security-awareness"
            />
          </div>
          <div className="row2">
            <div className="field">
              <label>
                Schedule launch <span className="hint">(optional — leave empty to launch now)</span>
              </label>
              <input
                type="datetime-local"
                value={f.launch_at}
                onChange={(e) => set("launch_at", e.target.value)}
              />
            </div>
            <div className="field">
              <label>
                Send by <span className="hint">(optional — drip sends until this time)</span>
              </label>
              <input
                type="datetime-local"
                value={f.send_by_at}
                onChange={(e) => set("send_by_at", e.target.value)}
                disabled={!scheduled}
              />
            </div>
          </div>
          {!scheduled && (
            <div className="field check">
              <input id="launch" type="checkbox" checked={launch} onChange={(e) => setLaunch(e.target.checked)} />
              <label htmlFor="launch">Launch immediately after creating</label>
            </div>
          )}
          <div className="btn-row" style={{ justifyContent: "flex-end" }}>
            <button type="button" className="btn" onClick={onClose}>
              Cancel
            </button>
            <button className="btn primary" disabled={busy}>
              {busy ? "Working…" : scheduled ? "Schedule campaign" : launch ? "Create & launch" : "Save draft"}
            </button>
          </div>
        </form>
      )}
    </Modal>
  );
}
