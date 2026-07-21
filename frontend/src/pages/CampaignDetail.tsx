import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, ApiError } from "../api";
import type { CampaignDetail as Detail, EventItem } from "../types";
import { Badge, CopyButton, DetailSkeleton, fmtDate } from "../components/ui";
import Donut from "../components/Donut";
import { useToast } from "../components/Toast";

const AUTO_REFRESH_MS = 2000; // live updates every 2s

export default function CampaignDetail() {
  const { id } = useParams();
  const cid = Number(id);
  const { notify } = useToast();
  const [c, setC] = useState<Detail | null>(null);
  const [events, setEvents] = useState<EventItem[]>([]);
  const [busy, setBusy] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);
  const [auto, setAuto] = useState(true);
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

  // Live auto-refresh (toggleable). Keeps pulling so late opens/clicks show up.
  useEffect(() => {
    if (timer.current) window.clearInterval(timer.current);
    if (auto) timer.current = window.setInterval(() => load(), AUTO_REFRESH_MS);
    return () => {
      if (timer.current) window.clearInterval(timer.current);
    };
  }, [auto, load]);

  const launch = async () => {
    setBusy(true);
    try {
      await api.launchCampaign(cid);
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
          <span className="updated">
            {auto && <span className="live-dot" title="live" />}
            {updatedAt ? `updated ${updatedAt.toLocaleTimeString()}` : ""}
          </span>
          <button className="btn" onClick={() => load(true)} disabled={refreshing} title="Refresh now">
            <span className={refreshing ? "spin" : ""}>⟳</span> Refresh
          </button>
          <button className="btn sm" onClick={() => setAuto((a) => !a)} title="Toggle live auto-refresh">
            {auto ? "⏸ Live" : "▶ Live"}
          </button>
          <a className="btn" href={`/api/v1/campaigns/${cid}/results.csv`} download>
            ⭳ CSV
          </a>
          {(c.status === "draft" || c.status === "scheduled") && (
            <button className="btn primary" onClick={launch} disabled={busy}>
              {busy ? "Launching…" : c.status === "scheduled" ? "▶ Launch now" : "▶ Launch"}
            </button>
          )}
        </div>
      </div>

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
