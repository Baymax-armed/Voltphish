import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import type { Person } from "../types";
import { Empty, ListSkeleton, fmtDate } from "../components/ui";

type SortKey = "risk" | "targeted" | "opened" | "clicked" | "submitted" | "reported" | "trainings_completed" | "last_activity";

const RISK_RANK: Record<Person["risk"], number> = { high: 0, medium: 1, low: 2 };

const RISK_STYLE: Record<Person["risk"], { bg: string; fg: string; label: string }> = {
  high: { bg: "rgba(220,38,38,.16)", fg: "#f87171", label: "High" },
  medium: { bg: "rgba(234,179,8,.16)", fg: "#eab308", label: "Medium" },
  low: { bg: "rgba(34,197,94,.16)", fg: "#4ade80", label: "Low" },
};

export default function People() {
  const [people, setPeople] = useState<Person[] | null>(null);
  const [q, setQ] = useState("");
  const [sort, setSort] = useState<SortKey>("risk");
  const [dir, setDir] = useState<"asc" | "desc">("asc"); // asc = riskiest/most first for risk

  useEffect(() => {
    api.listPeople().then(setPeople).catch(() => setPeople([]));
  }, []);

  const rows = useMemo(() => {
    if (!people) return [];
    const needle = q.trim().toLowerCase();
    const filtered = needle
      ? people.filter((p) =>
          p.email.toLowerCase().includes(needle) ||
          `${p.first_name ?? ""} ${p.last_name ?? ""}`.toLowerCase().includes(needle))
      : people.slice();
    const val = (p: Person): number | string => {
      if (sort === "risk") return RISK_RANK[p.risk];
      if (sort === "last_activity") return p.last_activity ?? "";
      return p[sort];
    };
    filtered.sort((a, b) => {
      const av = val(a);
      const bv = val(b);
      let c = av < bv ? -1 : av > bv ? 1 : 0;
      // tie-break by failures then targeted so the table is stable & meaningful
      if (c === 0) c = b.clicked - a.clicked || b.targeted - a.targeted;
      return dir === "asc" ? c : -c;
    });
    return filtered;
  }, [people, q, sort, dir]);

  const th = (key: SortKey, label: string) => (
    <th
      className="sortable"
      style={{ cursor: "pointer", whiteSpace: "nowrap" }}
      onClick={() => {
        if (sort === key) setDir((d) => (d === "asc" ? "desc" : "asc"));
        else { setSort(key); setDir(key === "risk" ? "asc" : "desc"); }
      }}
      title="Click to sort"
    >
      {label}{sort === key ? (dir === "asc" ? " ▲" : " ▼") : ""}
    </th>
  );

  if (!people) return <ListSkeleton cols={6} />;

  const counts = { high: 0, medium: 0, low: 0 };
  for (const p of people) counts[p.risk]++;

  return (
    <>
      <div className="page-head">
        <div>
          <h1>People</h1>
          <div className="page-sub">
            Every recipient's risk across all campaigns — who keeps falling for it, and who's been trained.
          </div>
        </div>
        <input
          className="search"
          placeholder="Search name or email…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          style={{ minWidth: 220 }}
        />
      </div>

      {people.length === 0 ? (
        <div className="card">
          <Empty>No recipients yet. Launch a campaign and results will show up here.</Empty>
        </div>
      ) : (
        <>
          <div className="grid cols-3" style={{ marginBottom: 18 }}>
            {(["high", "medium", "low"] as const).map((r) => (
              <div className="card" key={r} style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <span className="pill" style={{ background: RISK_STYLE[r].bg, color: RISK_STYLE[r].fg }}>
                  {RISK_STYLE[r].label} risk
                </span>
                <strong style={{ fontSize: 22, fontVariantNumeric: "tabular-nums" }}>{counts[r]}</strong>
                <span className="page-sub">{counts[r] === 1 ? "person" : "people"}</span>
              </div>
            ))}
          </div>

          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Person</th>
                  {th("risk", "Risk")}
                  {th("targeted", "Sims")}
                  {th("opened", "Opened")}
                  {th("clicked", "Clicked")}
                  {th("submitted", "Submitted")}
                  {th("reported", "Reported")}
                  {th("trainings_completed", "Trained")}
                  {th("last_activity", "Last activity")}
                </tr>
              </thead>
              <tbody>
                {rows.map((p) => {
                  const name = [p.first_name, p.last_name].filter(Boolean).join(" ");
                  const rs = RISK_STYLE[p.risk];
                  return (
                    <tr key={p.email}>
                      <td>
                        <div style={{ display: "flex", flexDirection: "column" }}>
                          {name && <strong>{name}</strong>}
                          <span className="mono" style={{ color: "var(--text-dim)" }}>{p.email}</span>
                        </div>
                      </td>
                      <td><span className="pill" style={{ background: rs.bg, color: rs.fg }}>{rs.label}</span></td>
                      <td style={{ fontVariantNumeric: "tabular-nums" }}>{p.targeted}</td>
                      <td style={{ fontVariantNumeric: "tabular-nums" }}>{p.opened}</td>
                      <td style={{ fontVariantNumeric: "tabular-nums", color: p.clicked ? "var(--violet)" : undefined }}>{p.clicked}</td>
                      <td style={{ fontVariantNumeric: "tabular-nums", color: p.submitted ? "var(--bad)" : undefined }}>{p.submitted}</td>
                      <td style={{ fontVariantNumeric: "tabular-nums", color: p.reported ? "var(--good)" : undefined }}>{p.reported}</td>
                      <td style={{ fontVariantNumeric: "tabular-nums" }}>
                        {p.trainings_assigned
                          ? `${p.trainings_completed}/${p.trainings_assigned}`
                          : "—"}
                      </td>
                      <td>{fmtDate(p.last_activity)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <div className="page-sub" style={{ marginTop: 10 }}>
            Showing {rows.length} of {people.length} {people.length === 1 ? "person" : "people"}.
          </div>
        </>
      )}
    </>
  );
}
