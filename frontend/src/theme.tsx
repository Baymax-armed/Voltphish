import { useEffect, useState } from "react";

export type Theme = "dark" | "light";

const KEY = "voltphish-theme";

function apply(theme: Theme) {
  document.documentElement.setAttribute("data-theme", theme);
}

// Initialize before first paint (called from main).
export function initTheme(): Theme {
  const saved = (localStorage.getItem(KEY) as Theme) || "dark";
  apply(saved);
  return saved;
}

export function useTheme() {
  const [theme, setTheme] = useState<Theme>(
    () => (localStorage.getItem(KEY) as Theme) || "dark",
  );
  useEffect(() => {
    apply(theme);
    localStorage.setItem(KEY, theme);
  }, [theme]);
  const toggle = () => setTheme((t) => (t === "dark" ? "light" : "dark"));
  return { theme, toggle };
}
