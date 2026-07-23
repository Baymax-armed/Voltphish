import { useEffect, useState } from "react";
import { api, ApiError } from "../api";
import type { ApiProvider, DeliverabilityResult, HeaderItem, Profile, ProfileKind } from "../types";
import { BulkBar, Empty, ListSkeleton, Modal, RowMenu, useSelection } from "../components/ui";
import { confirmDialog } from "../components/dialog";
import { useToast } from "../components/Toast";

export default function Profiles() {
  const { notify } = useToast();
  const [items, setItems] = useState<Profile[] | null>(null);
  const [editing, setEditing] = useState<Profile | null>(null);
  const [creating, setCreating] = useState(false);
  const [consoleMode, setConsoleMode] = useState(false);
  const [verifying, setVerifying] = useState<number | null>(null);
  const [checkOpen, setCheckOpen] = useState(false);
  const { sel, toggle, clear, allToggle } = useSelection();

  const bulkDelete = async () => {
    if (!(await confirmDialog({ title: "Delete profiles", message: `Delete ${sel.size} profile${sel.size > 1 ? "s" : ""}?`, confirmLabel: "Delete", danger: true }))) return;
    let ok = 0;
    let fail = 0;
    for (const id of sel) {
      try {
        await api.deleteProfile(id);
        ok++;
      } catch {
        fail++;
      }
    }
    notify(fail ? `Deleted ${ok}; ${fail} still used by a campaign.` : `Deleted ${ok} profile${ok > 1 ? "s" : ""}.`, fail ? "error" : "ok");
    clear();
    load();
  };

  const load = () => api.listProfiles().then(setItems);
  useEffect(() => {
    load();
    api.getSettings().then((s) => setConsoleMode(s.mail_backend === "console")).catch(() => {});
  }, []);

  const verify = async (p: Profile) => {
    setVerifying(p.id);
    try {
      const res = await api.verifyProfile(p.id);
      notify(res.detail, "ok");
    } catch (e) {
      notify(e instanceof ApiError ? e.message : "Verify failed", "error");
    } finally {
      setVerifying(null);
    }
  };

  const remove = async (p: Profile) => {
    if (!(await confirmDialog({ title: "Delete profile", message: `Delete "${p.name}"?`, confirmLabel: "Delete", danger: true }))) return;
    try {
      await api.deleteProfile(p.id);
      notify("Profile deleted");
      load();
    } catch (e) {
      notify(e instanceof ApiError ? e.message : "Delete failed", "error");
    }
  };

  if (!items) return <ListSkeleton cols={4} />;
  const ids = items.map((p) => p.id);
  const allChecked = ids.length > 0 && ids.every((id) => sel.has(id));

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Sending Profiles</h1>
          <div className="page-sub">SMTP servers used to deliver simulations. Passwords are encrypted at rest.</div>
        </div>
        <div className="btn-row">
          <button className="btn" onClick={() => setCheckOpen(true)} title="Check a domain's SPF/DKIM/DMARC">
            🔍 Check deliverability
          </button>
          <button className="btn primary" onClick={() => setCreating(true)}>
            + New profile
          </button>
        </div>
      </div>

      {checkOpen && <DeliverabilityModal onClose={() => setCheckOpen(false)} />}

      {consoleMode ? (
        <div className="banner" style={{ borderColor: "var(--warn)", color: "var(--warn)", background: "#2e2611" }}>
          ⚠️ <strong>DEV MODE (console backend):</strong> launching a campaign does <strong>NOT</strong> send real
          email — messages are written to <span className="mono">/data/outbox</span> as .eml files and everyone is
          marked "sent". To actually deliver, set <span className="mono">VOLTPHISH_MAIL_BACKEND=smtp</span> (in
          docker-compose.yml) and restart. <em>Verify</em> and <em>Send test</em> below always use real SMTP, so you
          can check your credentials regardless.
        </div>
      ) : (
        <div className="banner">
          ✅ SMTP mode: launched campaigns are delivered via the campaign's sending profile. Use <strong>Verify</strong>
          to confirm a profile's credentials connect and authenticate.
        </div>
      )}

      <BulkBar count={sel.size} noun="profile" onDelete={bulkDelete} onClear={clear} />

      {items.length === 0 ? (
        <div className="card">
          <Empty>No sending profiles yet.</Empty>
        </div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th className="check-col">
                  <input
                    type="checkbox"
                    aria-label="Select all"
                    checked={allChecked}
                    ref={(el) => {
                      if (el) el.indeterminate = sel.size > 0 && !allChecked;
                    }}
                    onChange={() => allToggle(ids)}
                  />
                </th>
                <th>Name</th>
                <th>From</th>
                <th>Delivery</th>
                <th>Security</th>
                <th className="actions-col"></th>
              </tr>
            </thead>
            <tbody>
              {items.map((p) => (
                <tr key={p.id} className={sel.has(p.id) ? "selected" : ""}>
                  <td className="check-col">
                    <input type="checkbox" aria-label={`Select ${p.name}`} checked={sel.has(p.id)} onChange={() => toggle(p.id)} />
                  </td>
                  <td>
                    <strong>{p.name}</strong>
                  </td>
                  <td>{p.from_address}</td>
                  <td className="mono">
                    {p.kind === "api" ? `API · ${p.api_provider}` : `${p.host}:${p.port}`}
                  </td>
                  <td>{p.kind === "api" ? "HTTPS" : p.use_ssl ? "SSL" : p.use_starttls ? "STARTTLS" : "none"}</td>
                  <td className="actions-col">
                    <div className="btn-row" style={{ justifyContent: "flex-end", flexWrap: "nowrap" }}>
                      <button className="btn sm" onClick={() => verify(p)} disabled={verifying === p.id}>
                        {verifying === p.id ? "Verifying…" : "✓ Verify"}
                      </button>
                      <RowMenu
                        items={[
                          { label: "Edit", icon: "✎", onClick: () => setEditing(p) },
                          { label: "Delete", icon: "🗑", danger: true, onClick: () => remove(p) },
                        ]}
                      />
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {(creating || editing) && (
        <ProfileForm
          profile={editing}
          onClose={() => {
            setCreating(false);
            setEditing(null);
          }}
          onSaved={() => {
            setCreating(false);
            setEditing(null);
            load();
          }}
        />
      )}
    </>
  );
}

const API_PROVIDERS: { value: ApiProvider; label: string; needsDomain?: boolean }[] = [
  { value: "brevo", label: "Brevo (Sendinblue) — 300/day free" },
  { value: "sendgrid", label: "SendGrid" },
  { value: "resend", label: "Resend" },
  { value: "postmark", label: "Postmark" },
  { value: "mailgun", label: "Mailgun (needs domain)", needsDomain: true },
];

function ProfileForm({
  profile,
  onClose,
  onSaved,
}: {
  profile: Profile | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const { notify } = useToast();
  const [kind, setKind] = useState<ProfileKind>(profile?.kind ?? "smtp");
  const [f, setF] = useState({
    name: profile?.name ?? "",
    from_address: profile?.from_address ?? "",
    envelope_sender: profile?.envelope_sender ?? "",
    host: profile?.host ?? "",
    port: profile?.port ?? 587,
    username: profile?.username ?? "",
    use_starttls: profile?.use_starttls ?? true,
    use_ssl: profile?.use_ssl ?? false,
    ignore_cert_errors: profile?.ignore_cert_errors ?? false,
    api_provider: (profile?.api_provider ?? "brevo") as ApiProvider,
    api_domain: profile?.api_domain ?? "",
  });
  const [password, setPassword] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [headers, setHeaders] = useState<HeaderItem[]>(profile?.headers ?? []);
  const [busy, setBusy] = useState(false);

  const set = (k: string, v: unknown) => setF((p) => ({ ...p, [k]: v }));
  const needsDomain = API_PROVIDERS.find((p) => p.value === f.api_provider)?.needsDomain;

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    const payload: Record<string, unknown> = {
      name: f.name,
      from_address: f.from_address,
      envelope_sender: f.envelope_sender || null,
      kind,
      headers: headers.filter((h) => h.key.trim()),
    };
    if (kind === "smtp") {
      Object.assign(payload, {
        host: f.host,
        port: f.port,
        username: f.username || null,
        use_starttls: f.use_starttls,
        use_ssl: f.use_ssl,
        ignore_cert_errors: f.ignore_cert_errors,
      });
      if (password) payload.password = password;
    } else {
      Object.assign(payload, {
        api_provider: f.api_provider,
        api_domain: needsDomain ? f.api_domain : null,
      });
      if (apiKey) payload.api_key = apiKey;
    }
    try {
      if (profile) await api.updateProfile(profile.id, payload);
      else await api.createProfile(payload);
      notify("Profile saved");
      onSaved();
    } catch (e) {
      notify(e instanceof ApiError ? e.message : "Save failed", "error");
      setBusy(false);
    }
  };

  const onPortChange = (port: number) => {
    setF((p) => {
      if (port === 465) return { ...p, port, use_ssl: true, use_starttls: false };
      if (port === 587 || port === 25) return { ...p, port, use_ssl: false, use_starttls: true };
      return { ...p, port };
    });
  };

  return (
    <Modal title={profile ? "Edit sending profile" : "New sending profile"} onClose={onClose}>
      <form onSubmit={save}>
        <div className="field">
          <label>Delivery type</label>
          <select value={kind} onChange={(e) => setKind(e.target.value as ProfileKind)}>
            <option value="smtp">SMTP server</option>
            <option value="api">Email API</option>
          </select>
        </div>
        <div className="field">
          <label>Profile name</label>
          <input value={f.name} onChange={(e) => set("name", e.target.value)} required />
        </div>
        <div className="field">
          <label>From address <span className="hint">(what the recipient sees — can be spoofed)</span></label>
          <input
            type="email"
            value={f.from_address}
            onChange={(e) => set("from_address", e.target.value)}
            placeholder="it-support@yourcompany.com"
            required
          />
        </div>
        {kind === "smtp" && (
          <div className="field">
            <label>
              Envelope sender <span className="hint">(optional — Return-Path for SPF; use an address your SMTP is authorized to send as)</span>
            </label>
            <input
              type="email"
              value={f.envelope_sender}
              onChange={(e) => set("envelope_sender", e.target.value)}
              placeholder="leave blank to use From — set an authorized address to spoof From & still pass SPF"
            />
          </div>
        )}

        {kind === "api" ? (
          <>
            <div className="banner">
              📡 Email-API mode sends over <strong>HTTPS (port 443)</strong> — no SMTP ports needed. Sign up with a
              provider, verify your sender/domain there, paste the API key, then hit <strong>Verify</strong>.
            </div>
            <div className="field">
              <label>Provider</label>
              <select value={f.api_provider} onChange={(e) => set("api_provider", e.target.value)}>
                {API_PROVIDERS.map((p) => (
                  <option key={p.value} value={p.value}>
                    {p.label}
                  </option>
                ))}
              </select>
            </div>
            {needsDomain && (
              <div className="field">
                <label>Sending domain <span className="hint">(Mailgun)</span></label>
                <input
                  value={f.api_domain}
                  onChange={(e) => set("api_domain", e.target.value)}
                  placeholder="mg.yourdomain.com"
                />
              </div>
            )}
            <div className="field">
              <label>
                API key <span className="hint">{profile?.has_api_key ? "(leave blank to keep)" : ""}</span>
              </label>
              <input
                type="password"
                value={apiKey}
                autoComplete="new-password"
                onChange={(e) => setApiKey(e.target.value)}
                placeholder="paste provider API key"
              />
            </div>
          </>
        ) : (
          <>
            <div className="row2">
              <div className="field">
                <label>SMTP host</label>
                <input value={f.host} onChange={(e) => set("host", e.target.value)} required />
              </div>
              <div className="field">
                <label>Port <span className="hint">587=STARTTLS · 465=SSL</span></label>
                <input type="number" value={f.port} onChange={(e) => onPortChange(Number(e.target.value))} required />
              </div>
            </div>
            <div className="row2">
              <div className="field">
                <label>Username <span className="hint">(optional)</span></label>
                <input value={f.username} onChange={(e) => set("username", e.target.value)} />
              </div>
              <div className="field">
                <label>
                  Password{" "}
                  <span className="hint">{profile?.has_password ? "(leave blank to keep)" : "(optional)"}</span>
                </label>
                <input type="password" value={password} autoComplete="new-password" onChange={(e) => setPassword(e.target.value)} />
              </div>
            </div>
            <div className="field check">
              <input id="starttls" type="checkbox" checked={f.use_starttls} onChange={(e) => set("use_starttls", e.target.checked)} />
              <label htmlFor="starttls">Use STARTTLS (port 587)</label>
            </div>
            <div className="field check">
              <input id="ssl" type="checkbox" checked={f.use_ssl} onChange={(e) => set("use_ssl", e.target.checked)} />
              <label htmlFor="ssl">Use implicit SSL/TLS (port 465)</label>
            </div>
            <div className="field check">
              <input id="ignore" type="checkbox" checked={f.ignore_cert_errors} onChange={(e) => set("ignore_cert_errors", e.target.checked)} />
              <label htmlFor="ignore">
                Ignore TLS certificate errors <span className="hint">(lab/self-signed only)</span>
              </label>
            </div>
          </>
        )}

        <div className="field">
          <label style={{ display: "flex", justifyContent: "space-between" }}>
            <span>Custom headers <span className="hint">(optional, e.g. X-Mailer)</span></span>
            <button type="button" className="btn sm" onClick={() => setHeaders([...headers, { key: "", value: "" }])}>
              + Add header
            </button>
          </label>
          {headers.map((h, i) => (
            <div key={i} style={{ display: "flex", gap: 8, marginBottom: 6 }}>
              <input placeholder="Header" value={h.key}
                onChange={(e) => setHeaders(headers.map((x, j) => (j === i ? { ...x, key: e.target.value } : x)))} />
              <input placeholder="Value" value={h.value}
                onChange={(e) => setHeaders(headers.map((x, j) => (j === i ? { ...x, value: e.target.value } : x)))} />
              <button type="button" className="btn sm danger" onClick={() => setHeaders(headers.filter((_, j) => j !== i))}>
                ✕
              </button>
            </div>
          ))}
        </div>

        <div className="btn-row" style={{ justifyContent: "flex-end" }}>
          <button type="button" className="btn" onClick={onClose}>
            Cancel
          </button>
          <button className="btn primary" disabled={busy}>
            {busy ? "Saving…" : "Save profile"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

function DeliverabilityModal({ onClose }: { onClose: () => void }) {
  const { notify } = useToast();
  const [domain, setDomain] = useState("");
  const [selector, setSelector] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<DeliverabilityResult | null>(null);

  const run = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setResult(null);
    try {
      const r = await api.checkDeliverability(domain.trim(), selector.trim() || null);
      setResult(r);
    } catch (err) {
      notify(err instanceof ApiError ? err.message : "Check failed", "error");
    } finally {
      setBusy(false);
    }
  };

  const dot = (s: string) =>
    s === "pass" ? "✅" : s === "warn" ? "🟡" : s === "skip" ? "⚪" : "❌";
  const verdictColor =
    result?.verdict === "good" ? "var(--good)" : result?.verdict === "partial" ? "#d4a017" : "var(--bad)";

  return (
    <Modal title="🔍 Deliverability pre-flight" onClose={onClose}>
      <div className="page-sub" style={{ marginBottom: 14 }}>
        Check a sending domain's SPF / DKIM / DMARC before launching. Weak records → simulations land in spam.
      </div>
      <form onSubmit={run}>
        <div className="row2">
          <div className="field">
            <label>From-domain</label>
            <input value={domain} onChange={(e) => setDomain(e.target.value)} placeholder="example.com" required />
          </div>
          <div className="field">
            <label>DKIM selector <span className="hint">(optional)</span></label>
            <input value={selector} onChange={(e) => setSelector(e.target.value)} placeholder="default, s1, google…" />
          </div>
        </div>
        <div className="btn-row" style={{ justifyContent: "flex-end", marginBottom: 6 }}>
          <button className="btn primary" disabled={busy || domain.trim().length < 3}>
            {busy ? "Checking DNS…" : "Run check"}
          </button>
        </div>
      </form>

      {result && (
        <div style={{ marginTop: 10 }}>
          <div className="card" style={{ borderLeft: `4px solid ${verdictColor}`, marginBottom: 12 }}>
            <strong style={{ color: verdictColor, textTransform: "uppercase", fontSize: 13 }}>{result.verdict}</strong>
            <div style={{ fontSize: 14, marginTop: 4 }}>{result.summary}</div>
          </div>
          {result.checks.map((c) => (
            <div key={c.key} className="card" style={{ marginBottom: 8 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <strong>{dot(c.status)} {c.label}</strong>
                <span className="hint" style={{ textTransform: "uppercase" }}>{c.status}</span>
              </div>
              <div className="hint" style={{ marginTop: 4 }}>{c.note}</div>
              {c.record && (
                <div className="mono" style={{ fontSize: 11, marginTop: 6, wordBreak: "break-all", opacity: 0.8 }}>
                  {c.record}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </Modal>
  );
}
