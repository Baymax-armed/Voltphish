import { Component, type ReactNode } from "react";

// A failed dynamic import ("Loading chunk … failed", "Failed to fetch
// dynamically imported module") almost always means the app was redeployed and
// THIS tab is still running an old bundle whose hashed chunk no longer exists.
// Without a boundary that crashes the whole app to a blank white page — so we
// catch it, reload once to pull the fresh build, and otherwise show a friendly
// recoverable message instead of a white screen.
const CHUNK_RE = /dynamically imported module|Loading chunk|module script failed|Failed to fetch/i;

interface Props {
  children: ReactNode;
  /** Optional inline fallback (e.g. for a single widget) instead of the full-page one. */
  fallback?: ReactNode;
}

export class ErrorBoundary extends Component<Props, { error: Error | null }> {
  state = { error: null as Error | null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  componentDidCatch(error: Error) {
    if (CHUNK_RE.test(error.message || "")) {
      // Reload at most once per 8s window so a genuinely broken build can't loop.
      const last = Number(sessionStorage.getItem("vp-reload-at") || 0);
      if (Date.now() - last > 8000) {
        sessionStorage.setItem("vp-reload-at", String(Date.now()));
        window.location.reload();
      }
    }
    // eslint-disable-next-line no-console
    console.error("Caught by ErrorBoundary:", error);
  }

  private reload = () => {
    sessionStorage.removeItem("vp-reload-at");
    window.location.reload();
  };

  render() {
    if (!this.state.error) return this.props.children;
    if (this.props.fallback) return this.props.fallback;

    const stale = CHUNK_RE.test(this.state.error.message || "");
    return (
      <div style={{ maxWidth: 460, margin: "18vh auto", textAlign: "center", padding: "0 24px", fontFamily: "system-ui, sans-serif" }}>
        <div style={{ fontSize: 40, marginBottom: 8 }}>⚡</div>
        <h2 style={{ margin: "0 0 8px" }}>{stale ? "A new version is available" : "Something went wrong"}</h2>
        <p style={{ color: "#7d8ba5", marginBottom: 20 }}>
          {stale
            ? "This tab was running an older build. Reload to get the latest version."
            : "An unexpected error occurred. Reloading usually fixes it."}
        </p>
        <button
          onClick={this.reload}
          style={{ padding: "11px 24px", borderRadius: 10, border: 0, cursor: "pointer",
            fontWeight: 700, color: "#fff", background: "linear-gradient(135deg,#45aef7,#1f5fd6)" }}
        >
          Reload
        </button>
      </div>
    );
  }
}
