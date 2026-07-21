import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import type { AtRiskUser, AttackSurface, Benchmark, Campaign, Champion, DashboardData, GeoPoint, RiskOut, TimelinePoint } from "../types";
import { Badge, DashboardSkeleton, Empty, fmtDate } from "../components/ui";
import Donut from "../components/Donut";
import TimelineChart from "../components/TimelineChart";
import { useCountUp } from "../components/useCountUp";

function riskColor(level: string): string {
  switch (level) {
    case "critical": return "var(--bad)";
    case "high": return "#e8833a";
    case "medium": return "#d4a017";
    default: return "var(--good)";
  }
}

export default function Dashboard() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [campaigns, setCampaigns] = useState<Campaign[] | null>(null);
  const [atRisk, setAtRisk] = useState<AtRiskUser[]>([]);
  const [champions, setChampions] = useState<Champion[]>([]);
  const [risk, setRisk] = useState<RiskOut | null>(null);
  const [geo, setGeo] = useState<GeoPoint[]>([]);
  const [surface, setSurface] = useState<AttackSurface | null>(null);
  const [bench, setBench] = useState<Benchmark | null>(null);
  const [timeline, setTimeline] = useState<TimelinePoint[]>([]);

  useEffect(() => {
    api.getDashboard().then(setData);
    api.listCampaigns().then(setCampaigns);
    api.getAtRisk().then(setAtRisk).catch(() => {});
    api.getChampions().then(setChampions).catch(() => {});
    api.getRisk().then(setRisk).catch(() => {});
    api.getGeo().then(setGeo).catch(() => {});
    api.getAttackSurface().then(setSurface).catch(() => {});
    api.getBenchmark().then(setBench).catch(() => {});
    api.getTimeline().then(setTimeline).catch(() => {});
  }, []);

  if (!data || !campaigns) return <DashboardSkeleton />;

  const f = data.funnel;
  const c = data.campaigns;

  const funnelSteps = [
    { label: "Email sent", value: f.sent, color: "var(--good)" },
    { label: "Opened", value: f.opened, color: "var(--accent)" },
    { label: "Clicked link", value: f.clicked, color: "var(--violet)" },
    { label: "Submitted data", value: f.submitted, color: "var(--bad)" },
    { label: "Reported", value: f.reported, color: "#22c55e" },
  ];

  const statusSegs = [
    { label: "Completed", value: c.completed, color: "var(--good)" },
    { label: "Active", value: c.active, color: "var(--warn)" },
    { label: "Scheduled", value: c.scheduled, color: "var(--accent)" },
    { label: "Draft", value: c.draft, color: "var(--text-dim)" },
  ];

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Dashboard</h1>
          <div className="page-sub">Program overview across all campaigns</div>
        </div>
        <div className="btn-row">
          <Link className="btn" to="/print-report" title="Board-level PDF report">
            📄 Export report
          </Link>
          <Link className="btn primary" to="/campaigns">
            + New campaign
          </Link>
        </div>
      </div>

      {/* Animated quick counts */}
      <div className="grid cols-4" style={{ marginBottom: 20 }}>
        <Stat label="Campaigns" value={c.total} to="/campaigns" cls="accent" delay={0} />
        <Stat label="Active now" value={c.active} cls={c.active ? "warn" : ""} delay={0.06} />
        <Stat label="Recipients" value={f.recipients} delay={0.12} />
        <Stat label="Templates" value={data.counts.templates} to="/templates" delay={0.18} />
      </div>

      {/* Activity-over-time graph */}
      <div className="card animate-in" style={{ marginBottom: 20, animationDelay: "0.08s" }}>
        <h2 style={{ margin: "0 0 4px", fontSize: 15 }}>Activity over time</h2>
        <div className="page-sub" style={{ marginBottom: 12 }}>Engagement events per day across all campaigns</div>
        <TimelineChart data={timeline} />
      </div>

      {/* Funnel bar chart */}
      <div className="card animate-in" style={{ marginBottom: 20, animationDelay: "0.12s" }}>
        <h2 style={{ margin: "0 0 4px", fontSize: 15 }}>Engagement funnel</h2>
        <div className="page-sub" style={{ marginBottom: 18 }}>{f.recipients} total recipients</div>
        <div className="funnel-bars">
          {funnelSteps.map((s, i) => (
            <FunnelBar key={s.label} {...s} total={f.recipients} delay={i * 0.1} />
          ))}
        </div>
      </div>

      <div className="grid cols-3" style={{ marginBottom: 20 }}>
        {/* Donut rings */}
        <div className="card animate-in" style={{ gridColumn: "span 2", animationDelay: "0.15s" }}>
          <h2 style={{ margin: "0 0 16px", fontSize: 15 }}>Success overview</h2>
          <div className="grid cols-5">
            <Donut value={f.sent} total={f.recipients} label="Sent" color="var(--good)" size={92} />
            <Donut value={f.opened} total={f.recipients} label="Opened" color="var(--accent)" size={92} />
            <Donut value={f.clicked} total={f.recipients} label="Clicked" color="var(--violet)" size={92} />
            <Donut value={f.submitted} total={f.recipients} label="Submitted" color="var(--bad)" size={92} />
            <Donut value={f.reported} total={f.recipients} label="Reported" color="#22c55e" size={92} />
          </div>
        </div>

        {/* Campaign status breakdown */}
        <div className="card animate-in" style={{ animationDelay: "0.2s" }}>
          <h2 style={{ margin: "0 0 4px", fontSize: 15 }}>Campaign status</h2>
          <div className="page-sub">{c.total} campaigns</div>
          <div className="status-bar">
            {statusSegs.map((s) => (
              <span key={s.label} style={{ flexGrow: s.value, background: s.color }} />
            ))}
          </div>
          <div className="status-legend" style={{ flexDirection: "column", gap: 8 }}>
            {statusSegs.map((s) => (
              <div className="item" key={s.label}>
                <span className="dot" style={{ background: s.color }} />
                {s.label} <b>{s.value}</b>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Human Risk Score — behaviour-based risk index */}
      {risk && risk.total_people > 0 && (
        <div className="card animate-in" style={{ marginBottom: 20, animationDelay: "0.2s" }}>
          <h2 style={{ margin: "0 0 4px", fontSize: 15 }}>🧠 Human Risk Score</h2>
          <div className="page-sub" style={{ marginBottom: 16 }}>
            Behaviour-based risk index (0–100) from clicks, submissions & reports across all simulations
          </div>
          <div style={{ display: "flex", gap: 28, flexWrap: "wrap", alignItems: "center" }}>
            <div style={{ textAlign: "center", minWidth: 150 }}>
              <div
                style={{
                  fontSize: 52, fontWeight: 800, lineHeight: 1,
                  color: riskColor(risk.overall_level),
                }}
              >
                {risk.overall_score}
              </div>
              <div
                className="badge"
                style={{
                  marginTop: 8, textTransform: "uppercase", letterSpacing: 0.5,
                  color: "#fff", background: riskColor(risk.overall_level),
                }}
              >
                {risk.overall_level} risk
              </div>
              <div className="hint" style={{ marginTop: 8 }}>{risk.total_people} people tracked</div>
            </div>
            <div style={{ flex: 1, minWidth: 260 }}>
              <div className="hint" style={{ marginBottom: 8 }}>Risk by department</div>
              {risk.departments.slice(0, 6).map((d) => (
                <div key={d.name} style={{ marginBottom: 9 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, marginBottom: 3 }}>
                    <span>{d.name} <span className="hint">({d.people})</span></span>
                    <strong style={{ color: riskColor(d.level) }}>{d.score}</strong>
                  </div>
                  <div style={{ height: 7, background: "var(--border)", borderRadius: 4, overflow: "hidden" }}>
                    <div style={{ width: `${d.score}%`, height: "100%", background: riskColor(d.level), transition: "width .6s ease" }} />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* At-risk users — who needs training */}
      {atRisk.length > 0 && (
        <div className="card animate-in" style={{ marginBottom: 20, animationDelay: "0.22s" }}>
          <h2 style={{ margin: "0 0 4px", fontSize: 15 }}>⚠️ At-risk users</h2>
          <div className="page-sub" style={{ marginBottom: 12 }}>
            Recipients who clicked or submitted most — prioritize these for awareness training
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Recipient</th>
                  <th>Clicked</th>
                  <th>Submitted data</th>
                  <th>Times targeted</th>
                </tr>
              </thead>
              <tbody>
                {atRisk.map((u) => (
                  <tr key={u.email}>
                    <td className="mono">{u.email}</td>
                    <td><span className="badge clicked">{u.clicked}</span></td>
                    <td>{u.submitted > 0 ? <span className="badge submitted">{u.submitted}</span> : <span className="hint">0</span>}</td>
                    <td>{u.total}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Geo breakdown — where clicks/submits came from */}
      {geo.length > 0 && (
        <div className="card animate-in" style={{ marginBottom: 20, animationDelay: "0.23s" }}>
          <h2 style={{ margin: "0 0 4px", fontSize: 15 }}>🌍 Where clicks came from</h2>
          <div className="page-sub" style={{ marginBottom: 14 }}>
            Geolocated click &amp; submit locations across all campaigns
          </div>
          {geo.map((g) => {
            const max = geo[0].count || 1;
            const flag = g.code
              ? g.code.toUpperCase().replace(/./g, (ch) => String.fromCodePoint(127397 + ch.charCodeAt(0)))
              : "🌐";
            return (
              <div key={g.country} style={{ marginBottom: 9 }}>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, marginBottom: 3 }}>
                  <span>{flag} {g.country}</span>
                  <strong>{g.count}</strong>
                </div>
                <div style={{ height: 7, background: "var(--border)", borderRadius: 4, overflow: "hidden" }}>
                  <div style={{ width: `${(g.count / max) * 100}%`, height: "100%", background: "var(--accent-grad)", transition: "width .6s ease" }} />
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Benchmark — org rates vs admin-configured industry baseline */}
      {bench && bench.enabled && (
        <div className="card animate-in" style={{ marginBottom: 20, animationDelay: "0.225s" }}>
          <h2 style={{ margin: "0 0 4px", fontSize: 15 }}>📊 You vs {bench.industry}</h2>
          <div className="page-sub" style={{ marginBottom: 14 }}>
            Your click &amp; report rates against the configured baseline (based on {bench.sample} results)
          </div>
          <div style={{ display: "flex", gap: 24, flexWrap: "wrap" }}>
            <BenchBar label="Click rate" your={bench.your_click_rate} base={bench.baseline_click_rate} lowerBetter />
            <BenchBar label="Report rate" your={bench.your_report_rate} base={bench.baseline_report_rate} />
          </div>
        </div>
      )}

      {/* Attack surface — most-targeted people and VIPs (VAP-style) */}
      {surface && surface.people.length > 0 && (
        <div className="card animate-in" style={{ marginBottom: 20, animationDelay: "0.235s" }}>
          <h2 style={{ margin: "0 0 4px", fontSize: 15 }}>🎯 Attack surface & VIPs</h2>
          <div className="page-sub" style={{ marginBottom: 12 }}>
            Most-targeted recipients and your high-value targets.{" "}
            {surface.vip_count > 0
              ? <><strong>{surface.vip_count}</strong> VIP{surface.vip_count === 1 ? "" : "s"} flagged · <strong>{surface.vip_failed}</strong> have failed a simulation.</>
              : <>Mark execs/finance/IT as ★ VIP in a group to track them here.</>}
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Recipient</th>
                  <th>Targeted</th>
                  <th>Failed</th>
                  <th>Risk</th>
                </tr>
              </thead>
              <tbody>
                {surface.people.map((p) => (
                  <tr key={p.email}>
                    <td>
                      {p.is_vip && <span title="VIP" style={{ color: "#f59e0b", marginRight: 6 }}>★</span>}
                      {p.email}
                    </td>
                    <td>{p.targeted}</td>
                    <td>{p.failed}</td>
                    <td>
                      <span className="pill" style={{ color: p.risk === "high" ? "#dc2626" : p.risk === "medium" ? "#d97706" : "#16a34a" }}>
                        {p.risk}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Security champions — who reports the phish (reward good instincts) */}
      {champions.length > 0 && (
        <div className="card animate-in" style={{ marginBottom: 20, animationDelay: "0.24s" }}>
          <h2 style={{ margin: "0 0 4px", fontSize: 15 }}>🏆 Security champions</h2>
          <div className="page-sub" style={{ marginBottom: 12 }}>
            Recipients who <strong>reported</strong> the simulated phish instead of falling for it — recognise these good instincts
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>#</th>
                  <th>Recipient</th>
                  <th>Times reported</th>
                  <th>Times targeted</th>
                </tr>
              </thead>
              <tbody>
                {champions.map((u, i) => (
                  <tr key={u.email}>
                    <td>{i === 0 ? "🥇" : i === 1 ? "🥈" : i === 2 ? "🥉" : i + 1}</td>
                    <td className="mono">{u.email}</td>
                    <td><span className="badge reported">{u.reported}</span></td>
                    <td>{u.total}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Recent campaigns */}
      <div className="card animate-in" style={{ animationDelay: "0.25s" }}>
        <h2 style={{ margin: "0 0 14px", fontSize: 15 }}>Recent campaigns</h2>
        {campaigns.length === 0 ? (
          <Empty>
            No campaigns yet. <Link to="/campaigns">Create your first one →</Link>
          </Empty>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Channel</th>
                  <th>Status</th>
                  <th>Created</th>
                </tr>
              </thead>
              <tbody>
                {campaigns.slice(0, 8).map((cp) => (
                  <tr key={cp.id}>
                    <td>
                      <Link to={`/campaigns/${cp.id}`}>{cp.name}</Link>
                    </td>
                    <td>{cp.channel === "sms" ? "📱 SMS" : "📧 Email"}</td>
                    <td>
                      <Badge status={cp.status} />
                    </td>
                    <td>{fmtDate(cp.created_at)}</td>
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

function Stat({ label, value, cls, to, delay }: { label: string; value: number; cls?: string; to?: string; delay: number }) {
  const shown = useCountUp(value);
  const body = (
    <div className={`card stat animate-in${to ? " hover" : ""}`} style={{ animationDelay: `${delay}s` }}>
      <span className="stat-label">{label}</span>
      <span className={`stat-value ${cls ?? ""}`}>{shown}</span>
    </div>
  );
  return to ? (
    <Link to={to} style={{ textDecoration: "none" }}>
      {body}
    </Link>
  ) : (
    body
  );
}

function FunnelBar({ label, value, total, color, delay }: { label: string; value: number; total: number; color: string; delay: number }) {
  const [w, setW] = useState(0);
  const pct = total > 0 ? Math.round((value / total) * 100) : 0;
  useEffect(() => {
    const t = window.setTimeout(() => setW(pct), 80 + delay * 1000);
    return () => window.clearTimeout(t);
  }, [pct, delay]);
  return (
    <div className="funnel-bar-row">
      <span className="funnel-bar-label">
        <span className="dot" style={{ background: color }} />
        {label}
      </span>
      <div className="funnel-bar-track">
        <div className="funnel-bar-fill" style={{ width: `${w}%`, background: color }} />
      </div>
      <span className="funnel-bar-count">
        {value} <small>/ {pct}%</small>
      </span>
    </div>
  );
}

function BenchBar({ label, your, base, lowerBetter }: { label: string; your: number; base: number; lowerBetter?: boolean }) {
  const max = Math.max(your, base, 1);
  const better = lowerBetter ? your <= base : your >= base;
  const yourColor = better ? "#16a34a" : "#dc2626";
  return (
    <div style={{ flex: "1 1 240px", minWidth: 220 }}>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, marginBottom: 6 }}>
        <strong>{label}</strong>
        <span style={{ color: yourColor, fontWeight: 700 }}>
          you {your}% {better ? "✓" : "▲"}
        </span>
      </div>
      <div style={{ position: "relative", height: 10, background: "var(--border)", borderRadius: 5, marginBottom: 4 }}>
        <div style={{ width: `${(your / max) * 100}%`, height: "100%", background: yourColor, borderRadius: 5, transition: "width .6s ease" }} />
        <div title={`baseline ${base}%`} style={{ position: "absolute", top: -3, left: `${(base / max) * 100}%`, width: 2, height: 16, background: "var(--text)", opacity: 0.7 }} />
      </div>
      <div className="hint">baseline {base}%</div>
    </div>
  );
}
