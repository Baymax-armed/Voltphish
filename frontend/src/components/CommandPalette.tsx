import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTheme } from "../theme";
import { useAuth } from "../auth";

interface Cmd {
  label: string;
  hint?: string;
  run: () => void;
}

export default function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [idx, setIdx] = useState(0);
  const nav = useNavigate();
  const { toggle } = useTheme();
  const { logout, user } = useAuth();

  const commands: Cmd[] = useMemo(() => {
    const go = (to: string) => () => nav(to);
    const base: Cmd[] = [
      { label: "Dashboard", hint: "page", run: go("/") },
      { label: "Campaigns", hint: "page", run: go("/campaigns") },
      { label: "New campaign", hint: "action", run: go("/campaigns") },
      { label: "Email Templates", hint: "page", run: go("/templates") },
      { label: "Landing Pages", hint: "page", run: go("/pages") },
      { label: "Groups & Targets", hint: "page", run: go("/groups") },
      { label: "Sending Profiles", hint: "page", run: go("/profiles") },
      { label: "API Keys", hint: "page", run: go("/apikeys") },
      { label: "Documentation", hint: "page", run: go("/docs") },
      { label: "Toggle light / dark theme", hint: "action", run: toggle },
      { label: "Sign out", hint: "action", run: logout },
    ];
    if (user?.role === "admin") {
      base.splice(9, 0,
        { label: "Webhooks", hint: "page", run: go("/webhooks") },
        { label: "Users", hint: "page", run: go("/users") },
      );
    }
    return base;
  }, [nav, toggle, logout, user]);

  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((o) => !o);
        setQ("");
        setIdx(0);
      } else if (e.key === "Escape") {
        setOpen(false);
      }
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, []);

  const filtered = commands.filter((c) => c.label.toLowerCase().includes(q.toLowerCase()));
  const run = (i: number) => {
    const c = filtered[i];
    if (c) {
      c.run();
      setOpen(false);
    }
  };

  if (!open) return null;
  return (
    <div className="cmdk-back" onClick={() => setOpen(false)}>
      <div className="cmdk" onClick={(e) => e.stopPropagation()}>
        <input
          autoFocus
          placeholder="Type a command or page…"
          value={q}
          onChange={(e) => {
            setQ(e.target.value);
            setIdx(0);
          }}
          onKeyDown={(e) => {
            if (e.key === "ArrowDown") {
              e.preventDefault();
              setIdx((i) => Math.min(i + 1, filtered.length - 1));
            } else if (e.key === "ArrowUp") {
              e.preventDefault();
              setIdx((i) => Math.max(i - 1, 0));
            } else if (e.key === "Enter") {
              e.preventDefault();
              run(idx);
            }
          }}
        />
        <div className="cmdk-list">
          {filtered.map((c, i) => (
            <div
              key={c.label}
              className={`cmdk-item${i === idx ? " active" : ""}`}
              onMouseEnter={() => setIdx(i)}
              onClick={() => run(i)}
            >
              <span>{c.label}</span>
              {c.hint && <span className="hint">{c.hint}</span>}
            </div>
          ))}
          {filtered.length === 0 && <div className="cmdk-item hint">No matches</div>}
        </div>
        <div className="cmdk-foot">↑↓ navigate · ↵ select · Esc close</div>
      </div>
    </div>
  );
}
