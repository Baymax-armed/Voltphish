import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, ApiError } from "../api";
import type { CampaignDetail as Detail, EventItem, TrainingModule } from "../types";
import { Badge, CopyButton, DetailSkeleton, Modal, fmtDate } from "../components/ui";
import { TRAINING_OUTCOMES } from "./Training";
import Donut from "../components/Donut";
import { useToast } from "../components/Toast";

const AUTO_REFRESH_MS = 2000; // live updates every 2s

// Render the captured submitted fields (JSON) as key=value chips. Passwords and
// other secrets are never stored server-side, so they never appear here.
function capturedData(raw?: string | null) {
  const dim = { color: "var(--text-dim)" } as const;
  if (!raw) return <span style={dim}>—</span>;
  let obj: Record<string, unknown>;
  try {
    obj = JSON.parse(raw);
  } catch {
    return <span style={dim}>—</span>;
  }
  const entries = Object.entries(obj || {});
  if (!entries.length) return <span style={dim}>—</span>;
  return (
    <span
      className="mono"
      style={{ fontSize: 12, display: "inline-flex", flexWrap: "wrap", gap: "3px 14px" }}
    >
      {entries.map(([k, v]) => (
        <span key={k}>
          <span style={dim}>{k}=</span>
          <span>{String(v)}</span>
        </span>
      ))}
    </span>
  );
}

export default function CampaignDetail() {
  const { id } = useParams();
  const cid = Number(id);
  const { notify } = useToast();
  const [c, setC] = useState<Detail | null>(null);
  const [events, setEvents] = useState<EventItem[]>([]);
  const [busy, setBusy] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);
  const [nowTick, setNowTick] = useState(0); // re-renders the "updated Xs ago" label
  const [auto, setAuto] = useState(true);
  const [launchOpen, setLaunchOpen] = useState(false);
  const [trainOpen, setTrainOpen] = useState<string>("");
  const [groupOpen, setGroupOpen] = useState(false);
  const timer = useRef<number | null>(null);

  const load = useCallback(
    async (manual = false) => {
      if (manual) setRefreshing(true);
      try {
        const [detail, ev] = await Promise.all([api.getCampaign(cid), api.campaignEvents(cid)]);
        setC(detail);
        setEvents(ev);
        setUpdatedAt(new Date());
        return detail;
      } finally {
        if (manual) setRefreshing(false);
      }
    },
    [cid],
  );

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cid]);

  // Tick every 5s so the "updated Xs ago" label stays current even when paused.
  useEffect(() => {
    const id = window.setInterval(() => setNowTick((t) => t + 1), 5000);
    return () => window.clearInterval(id);
  }, []);

  // Keep auto-refreshing after the send completes too: opens, clicks, submits
  // and reports keep arriving for a while afterwards, so the results should
  // update on their own without a manual Refresh. Only a draft (nothing sent
  // yet) or an errored campaign skips polling.
  const isLive =
    c?.status === "in_progress" || c?.status === "scheduled" || c?.status === "completed";
  // Poll fast while actively sending; gentler once completed (engagement only).
  const pollMs = c?.status === "completed" ? 6000 : AUTO_REFRESH_MS;

  // Live auto-refresh (toggleable). Keeps pulling so late opens/clicks show up,
  // and stops on its own when the campaign reaches a terminal state.
  useEffect(() => {
    if (timer.current) window.clearInterval(timer.current);
    if (auto && isLive) timer.current = window.setInterval(() => load(), pollMs);
    return () => {
      if (timer.current) window.clearInterval(timer.current);
    };
  }, [auto, isLive, pollMs, load]);

  const doLaunch = async (authorization_ref: string) => {
    setBusy(true);
    try {
      await api.launchCampaign(cid, { authorized: true, authorization_ref });
      setLaunchOpen(false);
      notify("Campaign launched");
      await load(true);
    } catch (e) {
      notify(e instanceof ApiError ? e.message : "Launch failed", "error");
    } finally {
      setBusy(false);
    }
  };

  if (!c) return <DetailSkeleton />;

  const s = c.stats;
  const total = s.total || 0;

  return (
    <>
      <div className="page-head">
        <div>
          <div className="page-sub">
            <Link to="/campaigns">← Campaigns</Link>
          </div>
          <h1 style={{ display: "flex", alignItems: "center", gap: 12 }}>
            {c.name} <Badge status={c.status} />
          </h1>
        </div>
        <div className="btn-row" style={{ alignItems: "center" }}>
          <span className="updated" title={updatedAt ? updatedAt.toLocaleTimeString() : ""}>
            {auto && isLive && <span className="live-dot" title="live" />}
            {agoLabel(updatedAt, nowTick)}
          </span>
          <button className="btn" onClick={() => load(true)} disabled={refreshing} title="Refresh now">
            <span className={refreshing ? "spin" : ""}>⟳</span> Refresh
          </button>
          {isLive && (
            <button className="btn sm" onClick={() => setAuto((a) => !a)} title="Toggle live auto-refresh">
              {auto ? "⏸ Live" : "▶ Live"}
            </button>
          )}
          <a className="btn" href={`/api/v1/campaigns/${cid}/results.csv`} download>
            ⭳ CSV
          </a>
          {(s.clicked > 0 || s.submitted > 0 || s.opened > 0) && (
            <button className="btn" onClick={() => setTrainOpen("bulk")} title="Enrol people from this campaign into a training module">
              🎓 Assign training
            </button>
          )}
          {total > 0 && (
            <button className="btn" onClick={() => setGroupOpen(true)} title="Save these recipients as a reusable group to re-test later">
              💾 Save as group
            </button>
          )}
          {(c.status === "draft" || c.status === "scheduled") && (
            <button className="btn primary" onClick={() => setLaunchOpen(true)} disabled={busy}>
              {c.status === "scheduled" ? "▶ Launch now" : "▶ Launch"}
            </button>
          )}
        </div>
      </div>

      {launchOpen && <LaunchDialog busy={busy} onCancel={() => setLaunchOpen(false)} onConfirm={doLaunch} />}

      {trainOpen && (
        <CampaignTrainingModal
          campaignId={cid}
          campaignName={c.name}
          singleEmail={trainOpen === "bulk" ? null : trainOpen}
          onClose={() => setTrainOpen("")}
          onDone={(msg) => { setTrainOpen(""); notify(msg, "ok"); }}
        />
      )}

      {groupOpen && (
        <SaveGroupModal
          campaignId={cid}
          campaignName={c.name}
          onClose={() => setGroupOpen(false)}
          onDone={(msg) => { setGroupOpen(false); notify(msg, "ok"); }}
        />
      )}

      {c.status === "scheduled" && c.launch_at && (
        <div className="banner">
          🕑 Scheduled for <strong>{fmtDate(c.launch_at)}</strong>
          {c.send_by_at && <> · dripped through <strong>{fmtDate(c.send_by_at)}</strong></>}. You can also launch now.
        </div>
      )}

      {/* Funnel donuts (Gophish-style) */}
      <div className="card" style={{ marginBottom: 20 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
          <h2 style={{ margin: 0, fontSize: 15 }}>Delivery → engagement</h2>
          <span className="page-sub">{total} recipients</span>
        </div>
        <div className="grid cols-5">
          <Donut value={s.sent} total={total} label="Sent" color="var(--good)" />
          <Donut value={s.opened} total={total} label="Opened" color="var(--accent)" />
          <Donut value={s.clicked} total={total} label="Clicked" color="var(--violet)" />
          <Donut value={s.submitted} total={total} label="Submitted" color="var(--bad)" />
          <Donut value={s.reported} total={total} label="Reported" color="var(--good)" />
        </div>
        {s.error > 0 && (
          <div className="page-sub" style={{ marginTop: 12, color: "var(--bad)" }}>
            ⚠ {s.error} send error(s) — see the recipients table for details.
          </div>
        )}
      </div>

      <div className="card" style={{ marginBottom: 20 }}>
        <h2 style={{ margin: "0 0 14px", fontSize: 15 }}>Recipients</h2>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Email</th>
                <th>Name</th>
                <th>Status</th>
                <th>Sent</th>
                <th>Last activity</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {c.results.map((r) => (
                <tr key={r.id}>
                  <td className="mono">
                    <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
                      {r.email}
                      <CopyButton label="Link" text={`${window.location.origin}/c/${r.rid}`} />
                    </span>
                  </td>
                  <td>{[r.first_name, r.last_name].filter(Boolean).join(" ") || "—"}</td>
                  <td>
                    <Badge status={r.status} />
                    {r.attachment_opened_at && (
                      <span className="badge opened" style={{ marginLeft: 6 }} title="Opened a tracked attachment">
                        📎 attachment
                      </span>
                    )}
                    {r.send_error && (
                      <span className="hint" style={{ marginLeft: 6 }}>
                        {r.send_error}
                      </span>
                    )}
                  </td>
                  <td>{fmtDate(r.sent_at)}</td>
                  <td>{fmtDate(r.last_event_at)}</td>
                  <td>
                    <button className="btn sm ghost" title={`Assign training to ${r.email}`}
                      onClick={() => setTrainOpen(r.email)}>
                      🎓 Train
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="card">
        <h2 style={{ margin: "0 0 14px", fontSize: 15 }}>Timeline</h2>
        {events.length === 0 ? (
          <div className="hint">No events yet.</div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Event</th>
                  <th>Captured data</th>
                  <th>Recipient</th>
                  <th>IP</th>
                </tr>
              </thead>
              <tbody>
                {events
                  .slice()
                  .reverse()
                  .map((e) => (
                    <tr key={e.id}>
                      <td>{fmtDate(e.created_at)}</td>
                      <td>
                        <Badge status={eventBadge(e.type)} />
                      </td>
                      <td>{capturedData(e.details)}</td>
                      <td className="mono">{ridEmail(c, e.rid)}</td>
                      <td className="mono">{e.ip || "—"}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  );
}

function agoLabel(d: Date | null, _tick: number): string {
  if (!d) return "";
  const s = Math.round((Date.now() - d.getTime()) / 1000);
  if (s < 5) return "updated just now";
  if (s < 60) return `updated ${s}s ago`;
  return `updated ${Math.round(s / 60)}m ago`;
}

function eventBadge(type: string): string {
  const map: Record<string, string> = {
    campaign_created: "draft",
    email_sent: "sent",
    email_error: "error",
    email_opened: "opened",
    clicked_link: "clicked",
    submitted_data: "submitted",
    reported: "reported",
  };
  return map[type] ?? "draft";
}

function ridEmail(c: Detail, rid: string | null): string {
  if (!rid) return "—";
  return c.results.find((r) => r.rid === rid)?.email ?? rid;
}

function CampaignTrainingModal({
  campaignId, campaignName, singleEmail, onClose, onDone,
}: {
  campaignId: number;
  campaignName: string;
  singleEmail: string | null;
  onClose: () => void;
  onDone: (msg: string) => void;
}) {
  const { notify } = useToast();
  const [modules, setModules] = useState<TrainingModule[]>([]);
  const [moduleId, setModuleId] = useState<number | "">("");
  const [outcome, setOutcome] = useState("clicked");
  const [preview, setPreview] = useState<{ count: number; total: number } | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.listModules().then((m) => {
      setModules(m);
      if (m.length === 1) setModuleId(m[0].id);
    }).catch(() => setModules([]));
  }, []);

  // Live "this will enrol N of M" preview for the bulk-by-outcome flow.
  useEffect(() => {
    if (singleEmail) { setPreview(null); return; }
    let alive = true;
    api.trainingAudience({ campaign_id: campaignId, outcome })
      .then((r) => { if (alive) setPreview(r); })
      .catch(() => { if (alive) setPreview(null); });
    return () => { alive = false; };
  }, [campaignId, outcome, singleEmail]);

  const submit = async () => {
    if (moduleId === "") { notify("Pick a training module", "error"); return; }
    setBusy(true);
    try {
      const r = singleEmail
        ? await api.assignModule(Number(moduleId), { emails: [singleEmail] })
        : await api.assignModule(Number(moduleId), { campaign_id: campaignId, outcome });
      onDone(r.detail);
    } catch (e) {
      notify(e instanceof ApiError ? e.message : "Assign failed", "error");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal
      title={singleEmail ? `Assign training to ${singleEmail}` : "Assign training from this campaign"}
      onClose={onClose}
    >
      <div className="field">
        <label>Training module</label>
        <select value={moduleId} onChange={(e) => setModuleId(e.target.value === "" ? "" : Number(e.target.value))}>
          <option value="">— pick a module —</option>
          {modules.map((m) => <option key={m.id} value={m.id}>{m.title}</option>)}
        </select>
        {modules.length === 0 && (
          <span className="hint" style={{ marginTop: 6 }}>
            No training modules yet — create one on the <Link to="/training">Training</Link> page first.
          </span>
        )}
      </div>

      {singleEmail ? (
        <div className="banner" style={{ margin: 0 }}>
          Enrols <strong>{singleEmail}</strong> and gives them a unique training link. Use <strong>✉ Email links</strong>
          {" "}on the Training page to send it.
        </div>
      ) : (
        <>
          <div className="field">
            <label>Who from “{campaignName}”</label>
            <select value={outcome} onChange={(e) => setOutcome(e.target.value)}>
              {TRAINING_OUTCOMES.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
            {preview && (
              <span className="hint" style={{ marginTop: 6 }}>
                This will enrol <strong style={{ color: "var(--accent)" }}>{preview.count}</strong> of {preview.total} recipient(s).
                Already-enrolled people are skipped.
              </span>
            )}
          </div>
        </>
      )}

      <div className="btn-row" style={{ justifyContent: "flex-end", marginTop: 16 }}>
        <button className="btn" onClick={onClose}>Cancel</button>
        <button className="btn primary" onClick={submit} disabled={busy || moduleId === ""}>
          {busy ? "Assigning…" : "Assign"}
        </button>
      </div>
    </Modal>
  );
}

function SaveGroupModal({
  campaignId, campaignName, onClose, onDone,
}: {
  campaignId: number;
  campaignName: string;
  onClose: () => void;
  onDone: (msg: string) => void;
}) {
  const { notify } = useToast();
  const [outcome, setOutcome] = useState("clicked");
  const [name, setName] = useState("");
  const [preview, setPreview] = useState<{ count: number; total: number } | null>(null);
  const [busy, setBusy] = useState(false);

  // Suggest a sensible default name that reflects the current filter.
  useEffect(() => {
    const label = TRAINING_OUTCOMES.find((o) => o.value === outcome)?.label ?? outcome;
    setName(`${campaignName} — ${label}`.slice(0, 120));
  }, [outcome, campaignName]);

  useEffect(() => {
    let alive = true;
    api.trainingAudience({ campaign_id: campaignId, outcome })
      .then((r) => { if (alive) setPreview(r); })
      .catch(() => { if (alive) setPreview(null); });
    return () => { alive = false; };
  }, [campaignId, outcome]);

  const submit = async () => {
    if (!name.trim()) { notify("Give the group a name", "error"); return; }
    setBusy(true);
    try {
      const r = await api.saveCampaignGroup(campaignId, { name: name.trim(), outcome });
      onDone(`Saved “${r.name}” with ${r.added} recipient(s).`);
    } catch (e) {
      notify(e instanceof ApiError ? e.message : "Save failed", "error");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal title="Save recipients as a group" onClose={onClose}>
      <div className="field">
        <label>Who to include</label>
        <select value={outcome} onChange={(e) => setOutcome(e.target.value)}>
          {TRAINING_OUTCOMES.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
        {preview && (
          <span className="hint" style={{ marginTop: 6 }}>
            <strong style={{ color: "var(--accent)" }}>{preview.count}</strong> of {preview.total} recipient(s)
            will be saved (deduped by email).
          </span>
        )}
      </div>
      <div className="field">
        <label>Group name</label>
        <input value={name} onChange={(e) => setName(e.target.value)} maxLength={120} placeholder="e.g. Q3 clickers — retest" />
      </div>
      <div className="banner" style={{ margin: 0 }}>
        Creates a reusable group you can target in a new campaign — the classic
        “re-test the people who fell for it” loop. Names are snapshotted from this campaign.
      </div>
      <div className="btn-row" style={{ justifyContent: "flex-end", marginTop: 16 }}>
        <button className="btn" onClick={onClose}>Cancel</button>
        <button className="btn primary" onClick={submit} disabled={busy || !name.trim() || (preview?.count ?? 1) === 0}>
          {busy ? "Saving…" : "Save group"}
        </button>
      </div>
    </Modal>
  );
}

function LaunchDialog({
  busy, onCancel, onConfirm,
}: { busy: boolean; onCancel: () => void; onConfirm: (ref: string) => void }) {
  const [ref, setRef] = useState("");
  const [ok, setOk] = useState(false);
  return (
    <Modal title="Confirm authorization to launch" onClose={onCancel}>
      <div className="banner" style={{ marginTop: 0 }}>
        ⚠️ Only launch against recipients you are <strong>authorized</strong> to test (your own org, or a client
        engagement with signed scope). Sending simulated phishing to people without consent may be illegal.
      </div>
      <div className="field">
        <label>Authorization reference <span className="hint">(ticket, scope doc, or approver — recorded in the audit log)</span></label>
        <input value={ref} onChange={(e) => setRef(e.target.value)} placeholder="e.g. SEC-1234 / signed scope 2026-07" />
      </div>
      <label className="field check" style={{ margin: "6px 0", cursor: "pointer" }}>
        <input type="checkbox" checked={ok} onChange={(e) => setOk(e.target.checked)} />
        <span>I confirm I am authorized to run this simulation against these recipients.</span>
      </label>
      <div className="btn-row" style={{ justifyContent: "flex-end", marginTop: 12 }}>
        <button className="btn" onClick={onCancel}>Cancel</button>
        <button className="btn primary" disabled={!ok || busy} onClick={() => onConfirm(ref.trim())}>
          {busy ? "Launching…" : "Launch campaign"}
        </button>
      </div>
    </Modal>
  );
}
