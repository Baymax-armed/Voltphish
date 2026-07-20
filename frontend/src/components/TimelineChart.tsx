import { useId } from "react";
import type { TimelinePoint } from "../types";

const SERIES = [
  { key: "sent", label: "Sent", color: "#34d399" },
  { key: "opened", label: "Opened", color: "#38bdf8" },
  { key: "clicked", label: "Clicked", color: "#a78bfa" },
  { key: "submitted", label: "Submitted", color: "#f87171" },
] as const;

function shortDate(iso: string): string {
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export default function TimelineChart({ data }: { data: TimelinePoint[] }) {
  const uid = useId().replace(/:/g, "");
  if (data.length < 2) {
    return (
      <div className="hint" style={{ padding: "30px 0", textAlign: "center" }}>
        Not enough activity yet — launch a campaign and engagement will chart here over time.
      </div>
    );
  }

  const W = 820;
  const H = 240;
  const pad = { l: 34, r: 14, t: 14, b: 30 };
  const max = Math.max(1, ...data.flatMap((d) => SERIES.map((s) => d[s.key])));
  const x = (i: number) => pad.l + (i / (data.length - 1)) * (W - pad.l - pad.r);
  const y = (v: number) => pad.t + (1 - v / max) * (H - pad.t - pad.b);

  const linePath = (key: string) =>
    data.map((d, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)},${y((d as any)[key]).toFixed(1)}`).join(" ");
  const areaPath = (key: string) =>
    `${linePath(key)} L${x(data.length - 1).toFixed(1)},${H - pad.b} L${x(0).toFixed(1)},${H - pad.b} Z`;

  const gridVals = [0, 0.5, 1];
  const step = Math.max(1, Math.ceil(data.length / 7));

  return (
    <div>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" style={{ display: "block" }} className="timeline-chart">
        <defs>
          {SERIES.map((s) => (
            <linearGradient id={`${uid}-${s.key}`} key={s.key} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={s.color} stopOpacity="0.28" />
              <stop offset="100%" stopColor={s.color} stopOpacity="0.02" />
            </linearGradient>
          ))}
        </defs>

        {/* horizontal gridlines + y labels */}
        {gridVals.map((t) => {
          const gy = pad.t + t * (H - pad.t - pad.b);
          return (
            <g key={t}>
              <line x1={pad.l} x2={W - pad.r} y1={gy} y2={gy} stroke="var(--border)" strokeWidth="1" />
              <text x={pad.l - 6} y={gy + 4} textAnchor="end" fontSize="10" fill="var(--text-dim)">
                {Math.round(max * (1 - t))}
              </text>
            </g>
          );
        })}

        {/* areas + lines */}
        {SERIES.map((s, si) => (
          <g key={s.key} className="chart-series" style={{ animationDelay: `${si * 0.12}s` }}>
            <path d={areaPath(s.key)} fill={`url(#${uid}-${s.key})`} />
            <path d={linePath(s.key)} fill="none" stroke={s.color} strokeWidth="2.4" strokeLinejoin="round" strokeLinecap="round" />
            {data.map((d, i) => (
              <circle key={i} cx={x(i)} cy={y((d as any)[s.key])} r="2.6" fill={s.color}>
                <title>{`${shortDate(d.date)} · ${s.label}: ${(d as any)[s.key]}`}</title>
              </circle>
            ))}
          </g>
        ))}

        {/* x labels */}
        {data.map((d, i) =>
          i % step === 0 || i === data.length - 1 ? (
            <text key={i} x={x(i)} y={H - 10} textAnchor="middle" fontSize="10.5" fill="var(--text-dim)">
              {shortDate(d.date)}
            </text>
          ) : null,
        )}
      </svg>

      <div className="status-legend" style={{ marginTop: 12, justifyContent: "center" }}>
        {SERIES.map((s) => (
          <div className="item" key={s.key}>
            <span className="dot" style={{ background: s.color, borderRadius: "50%" }} />
            {s.label}
          </div>
        ))}
      </div>
    </div>
  );
}
