import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import type { AtRiskUser, Campaign, DashboardData, RiskOut } from "../types";

// A print-optimized executive report. "Save as PDF" uses the browser's native
// print-to-PDF (window.print), so there is no server-side PDF dependency and it
// renders identically everywhere. The .no-print chrome is hidden when printing.
function riskColor(level: string): string {
  switch (level) {
    case "critical": return "#dc2626";
    case "high": return "#e8833a";
    case "medium": return "#d4a017";
    default: return "#16a34a";
  }
}

export default function Report() {
  const nav = useNavigate();
  const [data, setData] = useState<DashboardData | null>(null);
  const [risk, setRisk] = useState<RiskOut | null>(null);
  const [atRisk, setAtRisk] = useState<AtRiskUser[]>([]);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);

  useEffect(() => {
    api.getDashboard().then(setData);
    api.getRisk().then(setRisk).catch(() => {});
    api.getAtRisk().then(setAtRisk).catch(() => {});
    api.listCampaigns().then(setCampaigns).catch(() => {});
  }, []);

  if (!data) {
    return <div style={{ padding: 40, fontFamily: "system-ui" }}>Loading report…</div>;
  }

  const f = data.funnel;
  const pct = (n: number) => (f.sent > 0 ? Math.round((n / f.sent) * 100) : 0);
  const today = new Date().toLocaleDateString(undefined, { year: "numeric", month: "long", day: "numeric" });

  const metrics = [
    { label: "Emails sent", value: f.sent, sub: `${f.recipients} recipients` },
    { label: "Opened", value: f.opened, sub: `${pct(f.opened)}% of sent` },
    { label: "Clicked link", value: f.clicked, sub: `${pct(f.clicked)}% of sent` },
    { label: "Submitted data", value: f.submitted, sub: `${pct(f.submitted)}% of sent` },
    { label: "Reported phish", value: f.reported, sub: `${pct(f.reported)}% of sent` },
    { label: "Completed training", value: f.trained, sub: "acknowledged" },
  ];

  return (
    <div style={{ background: "#fff", color: "#111", minHeight: "100vh" }}>
      <style>{`
        @media print {
          .no-print { display: none !important; }
          @page { margin: 16mm; }
          body { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
        }
        .rpt { max-width: 900px; margin: 0 auto; padding: 32px 40px 60px; font-family: Segoe UI, system-ui, Arial, sans-serif; }
        .rpt h2 { font-size: 15px; margin: 30px 0 12px; border-bottom: 2px solid #eee; padding-bottom: 6px; }
        .rpt table { width: 100%; border-collapse: collapse; font-size: 13px; }
        .rpt th, .rpt td { text-align: left; padding: 7px 10px; border-bottom: 1px solid #eee; }
        .rpt th { color: #666; font-weight: 600; }
        .mcard { border: 1px solid #eaeaea; border-radius: 8px; padding: 14px 16px; }
      `}</style>

      <div className="no-print" style={{ background: "#f3f4f6", padding: "10px 40px", display: "flex", gap: 10, justifyContent: "flex-end", position: "sticky", top: 0, borderBottom: "1px solid #e5e7eb" }}>
        <button onClick={() => nav("/")} style={{ padding: "8px 16px", border: "1px solid #ccc", background: "#fff", borderRadius: 6, cursor: "pointer" }}>← Back</button>
        <button onClick={() => window.print()} style={{ padding: "8px 18px", border: "none", background: "#2563eb", color: "#fff", borderRadius: 6, cursor: "pointer", fontWeight: 600 }}>🖨 Save as PDF / Print</button>
      </div>

      <div className="rpt">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", borderBottom: "3px solid #2563eb", paddingBottom: 18 }}>
          <div>
            <div style={{ fontSize: 26, fontWeight: 800, letterSpacing: -0.5 }}>Security Awareness Report</div>
            <div style={{ color: "#666", marginTop: 4 }}>Phishing simulation program summary</div>
          </div>
          <div style={{ textAlign: "right", fontSize: 13, color: "#666" }}>
            <div style={{ fontWeight: 700, color: "#2563eb", fontSize: 16 }}>VoltPhish</div>
            <div>{today}</div>
          </div>
        </div>

        {risk && risk.total_people > 0 && (
          <div style={{ display: "flex", gap: 20, alignItems: "center", marginTop: 24, padding: 20, background: "#fafafa", borderRadius: 10 }}>
            <div style={{ textAlign: "center", minWidth: 120 }}>
              <div style={{ fontSize: 46, fontWeight: 800, color: riskColor(risk.overall_level), lineHeight: 1 }}>{risk.overall_score}</div>
              <div style={{ marginTop: 6, fontWeight: 700, textTransform: "uppercase", fontSize: 12, color: riskColor(risk.overall_level) }}>{risk.overall_level} risk</div>
            </div>
            <div style={{ fontSize: 14, color: "#444" }}>
              <strong>Human Risk Score</strong> across {risk.total_people} people and {data.campaigns.total} campaigns.
              This behaviour-based index (0–100) reflects click, submission and reporting rates. Lower is better;
              reporting phishing lowers the score.
            </div>
          </div>
        )}

        <h2>Program metrics</h2>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 12 }}>
          {metrics.map((m) => (
            <div key={m.label} className="mcard">
              <div style={{ fontSize: 26, fontWeight: 700 }}>{m.value}</div>
              <div style={{ fontSize: 13, fontWeight: 600 }}>{m.label}</div>
              <div style={{ fontSize: 12, color: "#888" }}>{m.sub}</div>
            </div>
          ))}
        </div>

        {risk && risk.departments.length > 0 && (
          <>
            <h2>Risk by department</h2>
            <table>
              <thead><tr><th>Department</th><th>People</th><th>Risk score</th><th>Level</th></tr></thead>
              <tbody>
                {risk.departments.map((d) => (
                  <tr key={d.name}>
                    <td>{d.name}</td>
                    <td>{d.people}</td>
                    <td><strong>{d.score}</strong></td>
                    <td style={{ color: riskColor(d.level), fontWeight: 600, textTransform: "capitalize" }}>{d.level}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}

        {atRisk.length > 0 && (
          <>
            <h2>Users needing attention</h2>
            <table>
              <thead><tr><th>Recipient</th><th>Clicked</th><th>Submitted</th><th>Times targeted</th></tr></thead>
              <tbody>
                {atRisk.map((u) => (
                  <tr key={u.email}>
                    <td>{u.email}</td><td>{u.clicked}</td><td>{u.submitted}</td><td>{u.total}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}

        <h2>Campaigns ({campaigns.length})</h2>
        <table>
          <thead><tr><th>Name</th><th>Channel</th><th>Status</th></tr></thead>
          <tbody>
            {campaigns.slice(0, 20).map((c) => (
              <tr key={c.id}>
                <td>{c.name}</td>
                <td>{c.channel === "sms" ? "SMS" : "Email"}</td>
                <td style={{ textTransform: "capitalize" }}>{String(c.status).replace(/_/g, " ")}</td>
              </tr>
            ))}
          </tbody>
        </table>

        <div style={{ marginTop: 40, paddingTop: 14, borderTop: "1px solid #eee", fontSize: 11, color: "#999" }}>
          Generated by VoltPhish · For authorized internal security-awareness training. Confidential.
        </div>
      </div>
    </div>
  );
}
