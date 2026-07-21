import { useEffect, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";

// ── Row action (kebab) menu ─────────────────────────────────────────────────
export type MenuItem = { label: string; onClick: () => void; danger?: boolean; icon?: string };

let menuSeq = 0;

export function RowMenu({ items }: { items: MenuItem[] }) {
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState<{ top?: number; bottom?: number; right: number }>({ right: 0 });
  const btnRef = useRef<HTMLButtonElement>(null);
  const idRef = useRef(0);
  if (!idRef.current) idRef.current = ++menuSeq;

  // Only one row menu may be open at a time: opening any menu broadcasts its id
  // and every other menu closes itself.
  useEffect(() => {
    const onOther = (e: Event) => {
      if ((e as CustomEvent).detail !== idRef.current) setOpen(false);
    };
    window.addEventListener("rowmenu-open", onOther);
    return () => window.removeEventListener("rowmenu-open", onOther);
  }, []);

  useEffect(() => {
    if (!open) return;
    const close = () => setOpen(false);
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    window.addEventListener("click", close);
    window.addEventListener("keydown", onKey);
    window.addEventListener("resize", close);
    window.addEventListener("scroll", close, true);
    return () => {
      window.removeEventListener("click", close);
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("resize", close);
      window.removeEventListener("scroll", close, true);
    };
  }, [open]);

  const toggle = (e: React.MouseEvent) => {
    e.stopPropagation();
    const willOpen = !open;
    if (willOpen) {
      const r = btnRef.current!.getBoundingClientRect();
      const estH = items.length * 40 + 14; // approx menu height
      const openUp = r.bottom + estH > window.innerHeight - 12;
      setPos({
        right: window.innerWidth - r.right,
        top: openUp ? undefined : r.bottom + 6,
        bottom: openUp ? window.innerHeight - r.top + 6 : undefined,
      });
      window.dispatchEvent(new CustomEvent("rowmenu-open", { detail: idRef.current }));
    }
    setOpen(willOpen);
  };

  return (
    <>
      <button ref={btnRef} className="btn sm kebab" onClick={toggle} aria-label="Row actions" aria-haspopup="menu" title="Actions">
        ⋯
      </button>
      {open &&
        createPortal(
          <div className="rowmenu" style={{ top: pos.top, bottom: pos.bottom, right: pos.right }} onClick={(e) => e.stopPropagation()} role="menu">
            {items.map((it, i) => (
              <button
                key={i}
                className={`rowmenu-item${it.danger ? " danger" : ""}`}
                role="menuitem"
                onClick={() => {
                  setOpen(false);
                  it.onClick();
                }}
              >
                {it.icon && <span className="rowmenu-ico">{it.icon}</span>}
                {it.label}
              </button>
            ))}
          </div>,
          document.body,
        )}
    </>
  );
}

// ── Multi-select helpers ────────────────────────────────────────────────────
export function useSelection() {
  const [sel, setSel] = useState<Set<number>>(new Set());
  const toggle = (id: number) =>
    setSel((s) => {
      const n = new Set(s);
      n.has(id) ? n.delete(id) : n.add(id);
      return n;
    });
  const clear = () => setSel(new Set());
  const allToggle = (ids: number[]) =>
    setSel((s) => (ids.every((id) => s.has(id)) ? new Set() : new Set(ids)));
  return { sel, toggle, clear, allToggle };
}

export function BulkBar({
  count,
  noun,
  onDelete,
  onClear,
}: {
  count: number;
  noun: string;
  onDelete: () => void;
  onClear: () => void;
}) {
  if (count === 0) return null;
  return (
    <div className="bulkbar">
      <span>
        <strong>{count}</strong> {noun}
        {count > 1 ? "s" : ""} selected
      </span>
      <div className="btn-row">
        <button className="btn sm danger" onClick={onDelete}>
          🗑 Delete selected
        </button>
        <button className="btn sm" onClick={onClear}>
          Clear
        </button>
      </div>
    </div>
  );
}

export function Modal({
  title,
  onClose,
  children,
  wide,
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
  wide?: boolean;
}) {
  // When the modal opens, the backdrop instantly covers the whole viewport —
  // including the button that opened it. A fast second click (a habitual
  // double-click) would otherwise land on the backdrop and dismiss the modal,
  // so it looks like the button "did nothing". Ignore backdrop clicks for a
  // short grace window after opening, and only when the press both began and
  // ended on the backdrop itself (so a drag-select ending outside won't close).
  const openedAt = useRef(0);
  const pressedBack = useRef(false);

  useEffect(() => {
    openedAt.current = performance.now();
    const h = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", h);
    // Lock body scroll while a modal is open.
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", h);
      document.body.style.overflow = "";
    };
  }, [onClose]);

  const onBackClick = (e: React.MouseEvent) => {
    if (e.target !== e.currentTarget || !pressedBack.current) return;
    if (performance.now() - openedAt.current < 400) return; // ignore the opening double-click's echo
    onClose();
  };

  // Portal to <body> so the backdrop always covers the whole viewport,
  // regardless of where in the tree the modal is rendered.
  return createPortal(
    <div
      className="modal-back"
      onMouseDown={(e) => { pressedBack.current = e.target === e.currentTarget; }}
      onClick={onBackClick}
    >
      <div className={`modal${wide ? " lg" : ""}`} onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <h2>{title}</h2>
          <button className="x" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>
        {children}
      </div>
    </div>,
    document.body,
  );
}

export function Badge({ status }: { status: string }) {
  return <span className={`badge ${status}`}>{status.replace("_", " ")}</span>;
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="empty">{children}</div>;
}

export function Spinner() {
  return <div className="loader-ring" role="status" aria-label="Loading" />;
}

export function Skeleton({ lines = 4 }: { lines?: number }) {
  return (
    <div className="card">
      {Array.from({ length: lines }).map((_, i) => (
        <div key={i} className="skeleton line" style={{ width: `${90 - i * 12}%` }} />
      ))}
    </div>
  );
}

const sk = (style: React.CSSProperties) => <span className="skeleton" style={{ display: "inline-block", ...style }} />;

export function TableSkeleton({ rows = 7, cols = 4 }: { rows?: number; cols?: number }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th className="check-col">{sk({ width: 16, height: 16, borderRadius: 4 })}</th>
            {Array.from({ length: cols }).map((_, i) => (
              <th key={i}>{sk({ height: 10, width: i === 0 ? 90 : 64, borderRadius: 5 })}</th>
            ))}
            <th className="actions-col" />
          </tr>
        </thead>
        <tbody>
          {Array.from({ length: rows }).map((_, r) => (
            <tr key={r}>
              <td className="check-col">{sk({ width: 16, height: 16, borderRadius: 4 })}</td>
              {Array.from({ length: cols }).map((_, c) => (
                <td key={c}>{sk({ height: 13, width: c === 0 ? "55%" : "40%", borderRadius: 6 })}</td>
              ))}
              <td className="actions-col">{sk({ width: 34, height: 26, borderRadius: 8 })}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function ListSkeleton({ cols = 4 }: { cols?: number }) {
  return (
    <>
      <div className="page-head">
        <div>
          {sk({ height: 22, width: 220, borderRadius: 7, marginBottom: 9 })}
          <br />
          {sk({ height: 12, width: 300, borderRadius: 6 })}
        </div>
        {sk({ height: 38, width: 160, borderRadius: 11 })}
      </div>
      <div style={{ marginBottom: 16 }}>{sk({ height: 40, width: 300, borderRadius: 10 })}</div>
      <TableSkeleton rows={7} cols={cols} />
    </>
  );
}

export function DashboardSkeleton() {
  return (
    <>
      <div className="page-head">
        <div>
          {sk({ height: 24, width: 170, borderRadius: 7, marginBottom: 9 })}
          <br />
          {sk({ height: 12, width: 260, borderRadius: 6 })}
        </div>
        {sk({ height: 38, width: 260, borderRadius: 11 })}
      </div>
      <div className="grid cols-4" style={{ marginBottom: 20 }}>
        {Array.from({ length: 4 }).map((_, i) => (
          <div className="card" key={i}>
            <div>{sk({ height: 11, width: "55%", borderRadius: 5, marginBottom: 14 })}</div>
            {sk({ height: 30, width: "45%", borderRadius: 7 })}
          </div>
        ))}
      </div>
      <div className="grid cols-3" style={{ marginBottom: 20 }}>
        {Array.from({ length: 3 }).map((_, i) => (
          <div className="card" key={i}>
            <div>{sk({ height: 13, width: "40%", borderRadius: 6, marginBottom: 16 })}</div>
            {sk({ height: 150, width: "100%", borderRadius: 10 })}
          </div>
        ))}
      </div>
      <div className="card">
        <div>{sk({ height: 13, width: "30%", borderRadius: 6, marginBottom: 14 })}</div>
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="skeleton line" style={{ width: `${88 - i * 10}%` }} />
        ))}
      </div>
    </>
  );
}

export function DetailSkeleton() {
  return (
    <>
      <div className="page-head">
        <div>
          {sk({ height: 24, width: 240, borderRadius: 7, marginBottom: 9 })}
          <br />
          {sk({ height: 12, width: 200, borderRadius: 6 })}
        </div>
        {sk({ height: 36, width: 120, borderRadius: 10 })}
      </div>
      <div className="grid cols-4" style={{ marginBottom: 20 }}>
        {Array.from({ length: 4 }).map((_, i) => (
          <div className="card" key={i}>
            <div>{sk({ height: 11, width: "55%", borderRadius: 5, marginBottom: 12 })}</div>
            {sk({ height: 28, width: "40%", borderRadius: 7 })}
          </div>
        ))}
      </div>
      <TableSkeleton rows={6} cols={4} />
    </>
  );
}

export function FormSkeleton({ fields = 4 }: { fields?: number }) {
  return (
    <div>
      {Array.from({ length: fields }).map((_, i) => (
        <div key={i} style={{ marginBottom: 14 }}>
          <div>{sk({ height: 11, width: 110, borderRadius: 5, marginBottom: 8 })}</div>
          {sk({ height: 38, width: "100%", borderRadius: 10 })}
        </div>
      ))}
    </div>
  );
}

export function CopyButton({ text, label = "Copy" }: { text: string; label?: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      type="button"
      className={`btn sm copy-btn${copied ? " copied" : ""}`}
      onClick={() => {
        navigator.clipboard?.writeText(text);
        setCopied(true);
        window.setTimeout(() => setCopied(false), 1500);
      }}
    >
      {copied ? "✓ Copied" : `⎘ ${label}`}
    </button>
  );
}

export function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}
