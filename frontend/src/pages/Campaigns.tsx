import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, ApiError } from "../api";
import type { Campaign, CampaignDetail, GroupSummary, PageSummary, Profile, Template, TrainingModule } from "../types";
import { Badge, BulkBar, Empty, FormSkeleton, ListSkeleton, Modal, RowMenu, fmtDate, useSelection } from "../components/ui";
import { confirmDialog } from "../components/dialog";
import { useToast } from "../components/Toast";

export default function Campaigns() {
  const { notify } = useToast();
  const nav = useNavigate();
  const [items, setItems] = useState<Campaign[] | null>(null);
  const [creating, setCreating] = useState(false);
  const [prefill, setPrefill] = useState<CampaignDetail | null>(null);
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

  // Clone opens the campaign form pre-filled with the source's settings so you
  // can tweak the copy before creating it — and it picks up a fresh public URL.
  const clone = async (c: Campaign) => {
    try {
      const detail = await api.getCampaign(c.id);
      setPrefill(detail);
    } catch (e) {
      notify(e instanceof ApiError ? e.message : "Couldn't open a copy", "error");
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
                  <td>
                    <Badge status={c.status} />
                  </td>
                  <td>{fmtDate(c.created_at)}</td>
                  <td className="actions-col">
                    <RowMenu
                      items={[
                        { label: "View", icon: "→", onClick: () => nav(`/campaigns/${c.id}`) },
                        { label: "Clone & edit", icon: "⧉", onClick: () => clone(c) },
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
      {prefill && <CampaignForm prefill={prefill} onClose={() => setPrefill(null)} />}
    </>
  );
}

function CampaignForm({ onClose, prefill }: { onClose: () => void; prefill?: CampaignDetail }) {
  const { notify } = useToast();
  const nav = useNavigate();
  const [templates, setTemplates] = useState<Template[]>([]);
  const [groups, setGroups] = useState<GroupSummary[]>([]);
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [pages, setPages] = useState<PageSummary[]>([]);
  const [modules, setModules] = useState<TrainingModule[]>([]);
  const [tunnel, setTunnel] = useState<{ configured: boolean; url: string | null } | null>(null);
  const [urlMode, setUrlMode] = useState<"tunnel" | "server" | "custom">("server");
  const [groupIds, setGroupIds] = useState<number[]>([]);
  const [excludeIds, setExcludeIds] = useState<number[]>([]);
  const [recip, setRecip] = useState<{ count: number; unique: number; excluded: number; duplicates: number } | null>(null);
  const [ready, setReady] = useState(false);
  const tz = Intl.DateTimeFormat().resolvedOptions().timeZone; // NG-011
  const [busy, setBusy] = useState(false);
  const [launch, setLaunch] = useState(true);
  const [authorized, setAuthorized] = useState(false);
  const [authRef, setAuthRef] = useState("");

  const [f, setF] = useState({
    name: prefill ? `${prefill.name} (copy)` : "",
    template_id: prefill?.template_id ?? 0,
    profile_id: prefill?.profile_id ?? 0,
    group_id: prefill?.group_id ?? 0,
    page_id: prefill?.page_id ?? 0, // 0 => built-in awareness page
    phish_url: window.location.origin, // refreshed below (fresh tunnel URL / prefill)
    redirect_url: prefill?.redirect_url ?? "",
    launch_at: "", // a clone starts as a fresh draft — no inherited schedule
    send_by_at: "",
    send_jitter: prefill?.send_jitter ?? false,
    business_hours_only: prefill?.business_hours_only ?? false,
    auto_enroll_trigger: prefill?.auto_enroll_trigger ?? "off", // off | clicked | submitted
    auto_enroll_module_id: prefill?.auto_enroll_module_id ?? 0, // 0 => adaptive pick
    auto_enroll_email: prefill?.auto_enroll_email ?? true,
  });
  const set = (k: string, v: unknown) => setF((p) => ({ ...p, [k]: v }));

  useEffect(() => {
    Promise.all([
      api.listTemplates(), api.listGroups(), api.listProfiles(), api.listPages(), api.listModules(),
    ]).then(([t, g, p, pg, m]) => {
      setTemplates(t);
      setGroups(g);
      setProfiles(p);
      setPages(pg);
      setModules(m);
      if (prefill) {
        setGroupIds(prefill.target_group_ids?.length ? prefill.target_group_ids : g[0] ? [g[0].id] : []);
        setExcludeIds(prefill.exclude_group_ids ?? []);
      } else {
        setF((prev) => ({
          ...prev,
          template_id: t[0]?.id ?? 0,
          group_id: g[0]?.id ?? 0,
          profile_id: p[0]?.id ?? 0,
        }));
        if (g[0]) setGroupIds([g[0].id]);
      }
      setReady(true);
    });
    // Detect a public Cloudflare Tunnel URL; if one is live, default to it so
    // recipients' links open on the public internet out of the box. A clone
    // deliberately re-detects here, so the copy captures the *current* public
    // URL rather than reusing the original campaign's (possibly stale) one.
    api.getTunnel().then((t) => {
      setTunnel(t);
      if (t.url) {
        setUrlMode("tunnel");
        setF((prev) => ({ ...prev, phish_url: t.url! }));
      } else if (prefill?.phish_url && !prefill.phish_url.includes("localhost")) {
        setUrlMode("custom");
        setF((prev) => ({ ...prev, phish_url: prefill.phish_url }));
      }
    }).catch(() => setTunnel({ configured: false, url: null }));
  }, []);

  // Live "X recipients (Y excluded, Z dupes removed)" preview (NG-001).
  useEffect(() => {
    if (groupIds.length === 0) { setRecip(null); return; }
    let alive = true;
    api.previewRecipients({ group_ids: groupIds, exclude_group_ids: excludeIds })
      .then((r) => { if (alive) setRecip(r); })
      .catch(() => { if (alive) setRecip(null); });
    return () => { alive = false; };
  }, [groupIds, excludeIds]);

  const toggleGroup = (kind: "inc" | "exc", id: number) => {
    const upd = (xs: number[]) => (xs.includes(id) ? xs.filter((x) => x !== id) : [...xs, id]);
    if (kind === "inc") setGroupIds(upd);
    else setExcludeIds(upd);
  };

  const refreshTunnel = () => {
    api.getTunnel().then((t) => {
      setTunnel(t);
      if (t.url) { setUrlMode("tunnel"); set("phish_url", t.url); }
    }).catch(() => {});
  };

  const pickUrlMode = (mode: "tunnel" | "server" | "custom") => {
    setUrlMode(mode);
    if (mode === "tunnel" && tunnel?.url) set("phish_url", tunnel.url);
    else if (mode === "server") set("phish_url", window.location.origin);
    else set("phish_url", ""); // custom: user types their own
  };

  const missing = ready && (!groups.length || !templates.length || !profiles.length);

  const scheduled = f.launch_at !== "";

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (launch && !scheduled && !authorized) {
      notify("Confirm you're authorized to test these recipients before launching.", "error");
      return;
    }
    if (groupIds.length === 0) {
      notify("Pick at least one target group.", "error");
      return;
    }
    setBusy(true);
    try {
      const created = await api.createCampaign({
        name: f.name,
        template_id: f.template_id,
        profile_id: f.profile_id,
        group_id: groupIds[0],
        group_ids: groupIds,
        exclude_group_ids: excludeIds,
        page_id: f.page_id || null,
        phish_url: f.phish_url,
        redirect_url: f.redirect_url || null,
        launch_at: f.launch_at ? new Date(f.launch_at).toISOString() : null,
        send_by_at: f.send_by_at ? new Date(f.send_by_at).toISOString() : null,
        send_jitter: f.send_jitter,
        business_hours_only: f.business_hours_only,
        send_timezone: tz,
        auto_enroll_trigger: f.auto_enroll_trigger,
        auto_enroll_module_id:
          f.auto_enroll_trigger !== "off" && f.auto_enroll_module_id ? f.auto_enroll_module_id : null,
        auto_enroll_email: f.auto_enroll_trigger !== "off" && f.auto_enroll_email,
      });
      if (scheduled) {
        notify("Campaign scheduled");
      } else if (launch) {
        await api.launchCampaign(created.id, { authorized: true, authorization_ref: authRef.trim() });
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
    <Modal title={prefill ? "Clone campaign — review & create" : "New campaign"} onClose={onClose}>
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
            <label>Email template</label>
            <select value={f.template_id} onChange={(e) => set("template_id", Number(e.target.value))}>
              {templates.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label>
              Target groups <span className="hint">pick one or more — combined &amp; deduped by email</span>
            </label>
            <div className="btn-row" style={{ flexWrap: "wrap" }}>
              {groups.map((g) => (
                <button
                  type="button"
                  key={g.id}
                  className={`btn sm ${groupIds.includes(g.id) ? "primary" : ""}`}
                  onClick={() => toggleGroup("inc", g.id)}
                >
                  {groupIds.includes(g.id) ? "✓ " : ""}{g.name} ({g.target_count})
                </button>
              ))}
            </div>
          </div>
          {groups.length > 1 && (
            <div className="field">
              <label>
                Exclude / never-phish <span className="hint">execs, recent leavers, opt-outs — removed from the send</span>
              </label>
              <div className="btn-row" style={{ flexWrap: "wrap" }}>
                {groups.map((g) => (
                  <button
                    type="button"
                    key={g.id}
                    className={`btn sm ${excludeIds.includes(g.id) ? "danger" : ""}`}
                    onClick={() => toggleGroup("exc", g.id)}
                    disabled={groupIds.includes(g.id) && groupIds.length === 1}
                    title={groupIds.includes(g.id) && groupIds.length === 1 ? "Can't exclude your only target group" : ""}
                  >
                    {excludeIds.includes(g.id) ? "✕ " : ""}{g.name}
                  </button>
                ))}
              </div>
            </div>
          )}
          {recip && (
            <div className="banner" style={{ margin: "0 0 14px" }}>
              📬 <strong>{recip.count}</strong> recipient{recip.count === 1 ? "" : "s"} will be targeted
              {recip.excluded > 0 && <> · {recip.excluded} excluded</>}
              {recip.duplicates > 0 && <> · {recip.duplicates} duplicate{recip.duplicates === 1 ? "" : "s"} removed</>}.
            </div>
          )}
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
          {(
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
              Phishing URL <span className="hint">where recipients' links open</span>
            </label>
            <select value={urlMode} onChange={(e) => pickUrlMode(e.target.value as "tunnel" | "server" | "custom")}>
              {tunnel?.url && <option value="tunnel">🌐 Public link — {tunnel.url}</option>}
              <option value="server">🖥 This server — {window.location.origin}</option>
              <option value="custom">✏️ Custom URL…</option>
            </select>
            {urlMode === "custom" && (
              <input
                style={{ marginTop: 8 }}
                value={f.phish_url}
                onChange={(e) => set("phish_url", e.target.value)}
                placeholder="https://your-public-host.example.com"
                required
              />
            )}
            {urlMode === "tunnel" && tunnel?.url && (
              <span className="hint" style={{ marginTop: 6, display: "block" }}>
                Links open at <span className="mono">{tunnel.url}</span> — a free public URL, no domain needed.
                To mint a <strong>fresh</strong> URL, restart the tunnel (<span className="mono">docker compose restart cloudflared</span>), then{" "}
                <button type="button" className="linklike" onClick={refreshTunnel} style={{ padding: 0 }}>↻ re-check</button>.
              </span>
            )}
            {urlMode === "server" && f.phish_url.includes("localhost") && (
              <span className="hint" style={{ marginTop: 6, display: "block", color: "var(--bad)" }}>
                ⚠ localhost only opens on this machine — recipients won't be able to reach it. Use a public link.
              </span>
            )}
            {tunnel?.configured && !tunnel.url && (
              <span className="hint" style={{ marginTop: 6, display: "block" }}>
                A Cloudflare Tunnel is configured but not running. Start it with{" "}
                <span className="mono">docker compose --profile tunnel up -d</span>.
              </span>
            )}
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
          <div className="field">
            <label>
              🎓 Auto-enrol failers in training <span className="hint">(close the loop automatically)</span>
            </label>
            <select value={f.auto_enroll_trigger} onChange={(e) => set("auto_enroll_trigger", e.target.value)}>
              <option value="off">Off — no automatic training</option>
              <option value="clicked">When someone clicks the link (or submits)</option>
              <option value="submitted">Only when someone submits data (worst offenders)</option>
            </select>
          </div>
          {f.auto_enroll_trigger !== "off" && (
            <div className="row2">
              <div className="field">
                <label>Module</label>
                <select value={f.auto_enroll_module_id} onChange={(e) => set("auto_enroll_module_id", Number(e.target.value))}>
                  <option value={0}>Adaptive — pick by how badly they failed</option>
                  {modules.map((m) => <option key={m.id} value={m.id}>{m.title}</option>)}
                </select>
              </div>
              <label className="field check" style={{ alignSelf: "end", cursor: "pointer" }}>
                <input type="checkbox" checked={f.auto_enroll_email} onChange={(e) => set("auto_enroll_email", e.target.checked)} />
                <span>Email the training link right away</span>
              </label>
            </div>
          )}
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
          <div className="hint" style={{ margin: "-6px 0 6px" }}>
            🕑 Times are in your local timezone (<strong>{tz}</strong>).
          </div>
          {scheduled && (
            <>
              <label className="field check" style={{ cursor: "pointer" }}>
                <input type="checkbox" checked={f.send_jitter} onChange={(e) => set("send_jitter", e.target.checked)} />
                <span>Jitter send times <span className="hint">— spread sends unevenly across the window (more realistic, kinder to spam filters)</span></span>
              </label>
              <label className="field check" style={{ cursor: "pointer" }}>
                <input type="checkbox" checked={f.business_hours_only} onChange={(e) => set("business_hours_only", e.target.checked)} />
                <span>Business hours only <span className="hint">— shift sends into Mon–Fri 09:00–17:00 ({tz})</span></span>
              </label>
            </>
          )}
          {!scheduled && (
            <div className="field check">
              <input id="launch" type="checkbox" checked={launch} onChange={(e) => setLaunch(e.target.checked)} />
              <label htmlFor="launch">Launch immediately after creating</label>
            </div>
          )}
          {!scheduled && launch && (
            <>
              <div className="field">
                <label>Authorization reference <span className="hint">(ticket / signed scope — audit-logged)</span></label>
                <input value={authRef} onChange={(e) => setAuthRef(e.target.value)} placeholder="e.g. SEC-1234" />
              </div>
              <label className="field check" style={{ cursor: "pointer" }}>
                <input type="checkbox" checked={authorized} onChange={(e) => setAuthorized(e.target.checked)} />
                <span>I confirm I'm authorized to run this simulation against these recipients.</span>
              </label>
            </>
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
