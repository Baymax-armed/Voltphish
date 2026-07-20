// VoltPhish anglerfish mark — aggressive spiky silhouette (dorsal spines, big
// toothy jaws, lure on a rod). Filled with currentColor so it adapts to the
// theme; pass a unique `id` per mounted instance for the eye mask.
export default function AnglerLogo({ id = "af" }: { id?: string }) {
  const e = `${id}Eye`;
  return (
    <svg viewBox="0 0 120 100" aria-hidden="true" fill="currentColor">
      <defs>
        <mask id={e}>
          <rect width="120" height="100" fill="#fff" />
          <circle cx="58" cy="47" r="3.6" fill="#000" />
        </mask>
      </defs>
      {/* lure rod + bulb */}
      <path d="M60 35 C62 14 90 12 94 32" fill="none" stroke="currentColor" strokeWidth="4" strokeLinecap="round" />
      <circle cx="95" cy="35" r="6.2" />
      <g mask={`url(#${e})`}>
        {/* body + tail */}
        <path d="M66 43 C62 35 50 33 40 35 C30 36 22 40 18 45 L7 38 L13 51 L7 64 L18 57 C24 67 40 71 52 69 C60 68 66 63 66 57 Z" />
        {/* dorsal spines */}
        <path d="M23 44 L26 28 L31 42 L33 26 L38 41 L40 24 L45 41 L47 25 L52 41 L54 28 L59 43 Z" />
        {/* upper jaw + teeth */}
        <path d="M64 43 L94 45 L98 49 L90 52 L88 47 L84 53 L82 47 L78 53 L76 47 L72 53 L70 47 L67 52 Z" />
        {/* lower jaw + teeth */}
        <path d="M64 60 L96 59 L99 55 L90 55 L88 61 L84 55 L82 61 L78 55 L76 61 L72 55 L70 61 L67 56 Z" />
      </g>
    </svg>
  );
}
