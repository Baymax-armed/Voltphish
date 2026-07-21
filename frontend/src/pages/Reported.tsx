import { useEffect, useState } from "react";
import { api, ApiError } from "../api";
import type { AddinConfig, ReportedEmail, ReportedSummary, ReportStatus } from "../types";
import { useToast } from "../components/Toast";

const STATUSES: ReportStatus[] = ["new", "reviewing", "malicious", "benign", "closed"];

const STATUS_COLORS: Record<ReportStatus, { bg: string; fg: string }> = {
  new: { bg: "#dbeafe", fg: "#1e40af" },
  reviewing: { bg: "#fef9c3", fg: "#854d0e" },
  malicious: { bg: "#fee2e2", fg: "#991b1b" },
  benign: { bg: "#dcfce7", fg: "#166534" },
  closed: { bg: "#f1f5f9", fg: "#475569" },
};

export default function Reported() {
  const { notify } = useToast();
  const [rows, setRows] = useState<ReportedEmail[] | null>(null);
  const [sum, setSum] = useState<ReportedSummary | null>(null);
  const [onlyReal, setOnlyReal] = useState(true);
  const [expanded, setExpanded] = useState<number | null>(null);

  const load = () => {
    api.listReported(onlyReal).then(setRows).catch(() => setRows([]));
    api.reportedSummary().then(setSum).catch(() => setSum(null));
  };
  useEffect(load, [onlyReal]);

  const setStatus = async (id: number, status: ReportStatus) => {
    try {
      const updated = await api.updateReported(id, { status });
      setRows((rs) => (rs || []).map((r) => (r.id === id ? updated : r)));
      api.reportedSummary().then(setSum).catch(() => {});
    } catch (err) {
      notify(err instanceof ApiError ? err.message : "Update failed", "error");
    }
  };

  const remove = async (id: number) => {
    try {
      await api.deleteReported(id);
      setRows((rs) => (rs || []).filter((r) => r.id !== id));
      api.reportedSummary().then(setSum).catch(() => {});
    } catch (err) {
      notify(err instanceof ApiError ? err.message : "Delete failed", "error");
    }
  };

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Reported Emails</h1>
          <div className="page-sub">Suspicious emails employees flagged with the Report-Phish button</div>
        </div>
      </div>

      {sum && (
        <div className="stat-row" style={{ display: "flex", gap: 12, marginBottom: 18, flexWrap: "wrap" }}>
          <StatCard label="Total reports" value={sum.total} />
          <StatCard label="Awaiting review" value={sum.new} accent="#1e40af" />
          <StatCard label="Real suspicious" value={sum.real} accent="#991b1b" />
          <StatCard label="Caught simulations" value={sum.simulations} accent="#166534" />
        </div>
      )}

      <AddinSetup />

      <div className="card" style={{ marginTop: 20 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
          <h2 style={{ margin: 0, fontSize: 16 }}>📨 Triage queue</h2>
          <label className="hint" style={{ display: "flex", alignItems: "center", gap: 6, cursor: "pointer" }}>
            <input type="checkbox" checked={onlyReal} onChange={(e) => setOnlyReal(e.target.checked)} />
            Hide caught simulations
          </label>
        </div>

        {!rows ? (
          <p className="hint">Loading…</p>
        ) : rows.length === 0 ? (
          <div className="banner" style={{ margin: 0 }}>
            No reports yet. Once employees install the Report-Phish button and flag an email, it shows up here.
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {rows.map((r) => {
              const c = STATUS_COLORS[r.status];
              const open = expanded === r.id;
              return (
                <div key={r.id} style={{ border: "1px solid var(--border, #e2e8f0)", borderRadius: 10, padding: 12 }}>
                  <div style={{ display: "flex", gap: 10, alignItems: "flex-start" }}>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                        {r.is_simulation ? (
                          <span className="pill" style={{ background: "#dcfce7", color: "#166534" }}>✓ simulation caught</span>
                        ) : (
                          <span className="pill" style={{ background: "#fee2e2", color: "#991b1b" }}>real report</span>
                        )}
                        <strong style={{ fontSize: 14 }}>{r.subject || "(no subject)"}</strong>
                      </div>
                      <div className="hint" style={{ marginTop: 4 }}>
                        From <span className="mono">{r.sender || "?"}</span> · reported by{" "}
                        <span className="mono">{r.reporter_email || "?"}</span> ·{" "}
                        {new Date(r.created_at).toLocaleString()}
                      </div>
                    </div>
                    <select
                      value={r.status}
                      onChange={(e) => setStatus(r.id, e.target.value as ReportStatus)}
                      style={{ background: c.bg, color: c.fg, border: 0, borderRadius: 6, padding: "4px 8px", fontWeight: 600 }}
                    >
                      {STATUSES.map((s) => (
                        <option key={s} value={s}>{s}</option>
                      ))}
                    </select>
                  </div>
                  <div style={{ display: "flex", gap: 12, marginTop: 8 }}>
                    {r.body_preview && (
                      <button className="linklike" style={linkBtn} onClick={() => setExpanded(open ? null : r.id)}>
                        {open ? "Hide message" : "View message"}
                      </button>
                    )}
                    <button className="linklike" style={{ ...linkBtn, color: "#991b1b" }} onClick={() => remove(r.id)}>
                      Delete
                    </button>
                  </div>
                  {open && r.body_preview && (
                    <pre
                      style={{
                        marginTop: 10, padding: 10, background: "var(--muted-bg, #f8fafc)", borderRadius: 8,
                        fontSize: 12, whiteSpace: "pre-wrap", wordBreak: "break-word", maxHeight: 300, overflow: "auto",
                      }}
                    >
                      {r.body_preview}
                    </pre>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </>
  );
}

const linkBtn: React.CSSProperties = {
  background: "none", border: "none", color: "var(--accent)", cursor: "pointer", padding: 0, fontSize: 13,
};

function StatCard({ label, value, accent }: { label: string; value: number; accent?: string }) {
  return (
    <div className="card" style={{ flex: "1 1 140px", padding: "14px 16px", margin: 0 }}>
      <div style={{ fontSize: 26, fontWeight: 700, color: accent || "var(--text)" }}>{value}</div>
      <div className="hint">{label}</div>
    </div>
  );
}

function AddinSetup() {
  const { notify } = useToast();
  const [cfg, setCfg] = useState<AddinConfig | null>(null);
  const [busy, setBusy] = useState(false);
  const [tab, setTab] = useState<"outlook" | "gmail">("outlook");

  useEffect(() => {
    api.addinConfig().then(setCfg).catch(() => setCfg(null));
  }, []);

  const copy = (text: string, what: string) => {
    navigator.clipboard?.writeText(text).then(
      () => notify(`${what} copied.`, "ok"),
      () => notify("Copy failed", "error"),
    );
  };

  const regen = async () => {
    if (!confirm("Regenerate the report token? Existing add-in installs will stop working until redeployed.")) return;
    setBusy(true);
    try {
      setCfg(await api.regenerateAddinToken());
      notify("Token regenerated. Redeploy the add-ins.", "ok");
    } catch (err) {
      notify(err instanceof ApiError ? err.message : "Failed", "error");
    } finally {
      setBusy(false);
    }
  };

  if (!cfg) return null;
  const origin = window.location.origin;
  const manifest = origin + cfg.manifest_url;
  const codeGs = origin + cfg.gmail_script_url;
  const appsJson = origin + "/addins/gmail/appsscript.json";

  const copyBtn = (text: string, what: string) => (
    <button type="button" className="btn sm" onClick={() => copy(text, what)}>Copy</button>
  );
  const linkBtn = (href: string, label: string) => (
    <a className="btn sm" href={href} target="_blank" rel="noopener noreferrer">{label}</a>
  );

  return (
    <div className="card">
      <h2 style={{ margin: "0 0 4px", fontSize: 16 }}>🔘 Install the Report-Phish button</h2>
      <p className="hint" style={{ marginBottom: 14 }}>
        Give employees a one-click button to report suspicious mail. Reports of your own simulations credit them as
        Security Champions automatically; real suspicious mail lands in the triage queue below. Follow the steps for
        your mail platform:
      </p>

      <div className="tabs" style={{ marginBottom: 4 }}>
        <button type="button" className={`tab ${tab === "outlook" ? "active" : ""}`} onClick={() => setTab("outlook")}>
          Outlook / Microsoft 365
        </button>
        <button type="button" className={`tab ${tab === "gmail" ? "active" : ""}`} onClick={() => setTab("gmail")}>
          Gmail / Google Workspace
        </button>
      </div>

      {tab === "outlook" ? (
        <div className="install">
          <div className="hint" style={{ fontWeight: 700, color: "var(--text)", margin: "12px 0 6px" }}>
            Roll out to everyone (recommended — needs a Microsoft 365 admin)
          </div>
          <ol className="steps">
            <li>Copy the add-in manifest URL:
              <div className="inline-copy"><input readOnly value={manifest} className="mono" />{copyBtn(manifest, "Manifest URL")}</div>
            </li>
            <li>Open the <strong>Microsoft 365 admin center</strong> → <strong>Settings → Integrated apps</strong> → <strong>Upload custom apps</strong>.</li>
            <li>Choose <strong>“Provide link to manifest file (URL)”</strong> and paste the URL from step&nbsp;1.</li>
            <li>Select the users / groups to give it to, then <strong>Deploy</strong>.</li>
            <li>The <strong>Report Phish</strong> button appears in their Outlook (desktop &amp; web) — usually within a few hours (up to ~24h to fully propagate).</li>
          </ol>
          <div className="hint" style={{ fontWeight: 700, color: "var(--text)", margin: "16px 0 6px" }}>
            Just test it yourself (no admin — sideload)
          </div>
          <ol className="steps">
            <li>In Outlook, open <strong>Get Add-ins → My add-ins → Custom Addins → Add a custom add-in → Add from URL</strong>.</li>
            <li>Paste the manifest URL above. The button shows up right away when you open a message.</li>
          </ol>
        </div>
      ) : (
        <div className="install">
          <ol className="steps">
            <li>Open <strong>Code.gs</strong> and copy everything in it:
              <div className="inline-copy" style={{ gap: 6 }}>{linkBtn(codeGs, "Open Code.gs")}</div>
            </li>
            <li>Go to <strong>script.google.com</strong> → <strong>New project</strong>. Delete the sample code and paste the <code>Code.gs</code> contents.</li>
            <li>Click <strong>Project Settings ⚙</strong> → tick <strong>“Show appsscript.json manifest file”</strong>. Open the <code>appsscript.json</code> tab, then open ours and paste its contents over it:
              <div className="inline-copy" style={{ gap: 6 }}>{linkBtn(appsJson, "Open appsscript.json")}</div>
            </li>
            <li><strong>Deploy → Test deployments → Install</strong> (approve the permissions prompt).</li>
            <li>Open any email in Gmail — the <strong>Report Phish</strong> card appears in the right-hand add-in panel.</li>
          </ol>
        </div>
      )}

      <div className="field" style={{ marginTop: 16 }}>
        <label>
          Report token <span className="hint">— embedded in the add-in; regenerate to revoke old installs</span>
        </label>
        <div style={{ display: "flex", gap: 6 }}>
          <input readOnly value={cfg.token} type="password" className="mono" style={{ flex: 1 }} />
          <button type="button" className="btn" onClick={() => copy(cfg.token, "Token")}>Copy</button>
          <button type="button" className="btn danger-solid" onClick={regen} disabled={busy}>
            {busy ? "…" : "Regenerate"}
          </button>
        </div>
      </div>

      <div className="banner" style={{ marginTop: 8, marginBottom: 0 }}>
        💡 The button posts to <span className="mono">{origin}/api/v1/inbound/report</span> — make sure this host is
        reachable over <strong>HTTPS</strong> from your users' mail clients (a public/company URL, not <code>localhost</code>).
      </div>
    </div>
  );
}
