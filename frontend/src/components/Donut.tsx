// A Gophish-style donut/ring showing a percentage with a labelled count.
export default function Donut({
  value,
  total,
  label,
  color,
  size = 96,
}: {
  value: number;
  total: number;
  label: string;
  color: string;
  size?: number;
}) {
  const pct = total > 0 ? Math.round((value / total) * 100) : 0;
  const stroke = 9;
  const r = (size - stroke) / 2;
  const circ = 2 * Math.PI * r;
  const offset = circ - (pct / 100) * circ;
  return (
    <div className="donut">
      <svg width={size} height={size}>
        <circle className="ring-track" cx={size / 2} cy={size / 2} r={r} fill="none" strokeWidth={stroke} />
        <circle
          className="ring-value"
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={color}
          strokeWidth={stroke}
          strokeDasharray={circ}
          strokeDashoffset={offset}
        />
        <text
          className="ring-center"
          x="50%"
          y="50%"
          dominantBaseline="central"
          textAnchor="middle"
          transform={`rotate(90 ${size / 2} ${size / 2})`}
        >
          {pct}%
        </text>
      </svg>
      <div className="donut-label">{label}</div>
      <div className="donut-count">
        {value} / {total}
      </div>
    </div>
  );
}
