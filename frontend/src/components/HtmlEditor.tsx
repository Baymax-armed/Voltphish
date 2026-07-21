import { lazy, Suspense, useRef, useState } from "react";
import { insertIntoEditor } from "./editorUtils";
import { ErrorBoundary } from "./ErrorBoundary";

// Lazy so the heavy CKEditor bundle loads only when an editor is opened.
const RichEditor = lazy(() => import("./RichEditor"));

export interface EditorVar {
  token: string;
  label: string;
}

const DEFAULT_VARS: EditorVar[] = [
  { token: "{{.FirstName}}", label: "First name" },
  { token: "{{.LastName}}", label: "Last name" },
  { token: "{{.Email}}", label: "Email" },
  { token: "{{.Position}}", label: "Position" },
  { token: "{{.URL}}", label: "Link" },
  { token: "{{.QR}}", label: "QR code" },
  { token: "{{.Tracker}}", label: "Open pixel" },
];

// A stand-in for the per-recipient QR in previews (the real one is generated at
// send time by the backend and points at the recipient's click link).
const QR_PLACEHOLDER =
  '<span style="display:inline-flex;align-items:center;justify-content:center;' +
  "width:120px;height:120px;border:2px solid #111;border-radius:6px;" +
  'font:600 11px system-ui;color:#111;background:repeating-conic-gradient(#111 0% 25%,#fff 0% 50%) 0/14px 14px">QR</span>';

function sample(html: string): string {
  return html
    .replace(/\{\{\.FirstName\}\}/g, "Alex")
    .replace(/\{\{\.LastName\}\}/g, "Kumar")
    .replace(/\{\{\.Email\}\}/g, "alex@example.com")
    .replace(/\{\{\.Position\}\}/g, "Finance")
    .replace(/\{\{\.URL\}\}/g, "#")
    .replace(/\{\{\.QRURL\}\}/g, "#")
    .replace(/\{\{\.QR\}\}/g, QR_PLACEHOLDER)
    .replace(/\{\{\.Tracker\}\}/g, "");
}

export default function HtmlEditor({
  value,
  onChange,
  variables = DEFAULT_VARS,
  height = 340,
}: {
  value: string;
  onChange: (html: string) => void;
  variables?: EditorVar[];
  height?: number;
}) {
  const [mode, setMode] = useState<"design" | "source" | "preview">("design");
  const editorRef = useRef<any>(null);

  const insertVar = (token: string) => {
    if (mode === "design" && editorRef.current) insertIntoEditor(editorRef.current, token);
    else onChange(value + token);
  };

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: 8, marginBottom: 8 }}>
        <div className="btn-row">
          <button type="button" className={`btn sm ${mode === "design" ? "primary" : ""}`} onClick={() => setMode("design")}>✎ Design</button>
          <button type="button" className={`btn sm ${mode === "source" ? "primary" : ""}`} onClick={() => setMode("source")}>{"</> HTML"}</button>
          <button type="button" className={`btn sm ${mode === "preview" ? "primary" : ""}`} onClick={() => setMode("preview")}>👁 Preview</button>
        </div>
        <div className="btn-row">
          {variables.map((v) => (
            <button key={v.token} type="button" className="btn sm" title={`Insert ${v.token}`} onClick={() => insertVar(v.token)}>
              {v.label}
            </button>
          ))}
        </div>
      </div>

      {mode === "design" && (
        <ErrorBoundary
          fallback={
            <div style={{ padding: 20, textAlign: "center", border: "1px solid var(--border)", borderRadius: 8 }}>
              <p style={{ margin: "0 0 10px", color: "var(--text-dim)" }}>
                Couldn't load the rich editor (the app may have just updated).
              </p>
              <button type="button" className="btn primary" onClick={() => window.location.reload()}>Reload</button>
            </div>
          }
        >
          <Suspense fallback={<div className="spinner">Loading editor…</div>}>
            <RichEditor value={value} onChange={onChange} onReady={(ed) => (editorRef.current = ed)} />
          </Suspense>
        </ErrorBoundary>
      )}
      {mode === "source" && (
        <textarea value={value} onChange={(e) => onChange(e.target.value)} rows={Math.round(height / 22)} />
      )}
      {mode === "preview" && (
        <iframe
          title="preview"
          sandbox=""
          style={{ width: "100%", height, border: "1px solid var(--border)", borderRadius: 8, background: "#fff" }}
          srcDoc={sample(value)}
        />
      )}
    </div>
  );
}
