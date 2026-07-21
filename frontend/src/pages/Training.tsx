import { useEffect, useState } from "react";
import { api, ApiError } from "../api";
import type { AutoEnrollConfig, Campaign, Difficulty, GroupSummary, Profile, QuizQuestion, RecommendationRow, TrainingModule, TrainingSummary, LeaderboardRow } from "../types";

export const TRAINING_OUTCOMES: { value: string; label: string }[] = [
  { value: "all", label: "Everyone in the campaign" },
  { value: "clicked", label: "Clicked the link (incl. submitters)" },
  { value: "submitted", label: "Submitted data (worst)" },
  { value: "opened", label: "Opened only (didn't click)" },
  { value: "reported", label: "Reported it (good instinct)" },
  { value: "no_action", label: "No action (didn't open)" },
];
import { useToast } from "../components/Toast";
import { Modal } from "../components/ui";
import { confirmDialog } from "../components/dialog";

const DIFFS: Difficulty[] = ["beginner", "intermediate", "advanced"];
const DIFF_COLOR: Record<Difficulty, string> = {
  beginner: "#16a34a",
  intermediate: "#d97706",
  advanced: "#dc2626",
};

const blankModule = (): Partial<TrainingModule> => ({
  title: "", description: "", category: "General", difficulty: "beginner",
  content_html: "", video_url: "", estimated_minutes: 5, pass_score: 80, points: 100,
  is_published: true, questions: [],
});

export default function Training() {
  const { notify } = useToast();
  const [mods, setMods] = useState<TrainingModule[] | null>(null);
  const [sum, setSum] = useState<TrainingSummary | null>(null);
  const [board, setBoard] = useState<LeaderboardRow[]>([]);
  const [editing, setEditing] = useState<Partial<TrainingModule> | null>(null);
  const [assigning, setAssigning] = useState<TrainingModule | null>(null);
  const [sending, setSending] = useState<TrainingModule | null>(null);

  const load = () => {
    api.listModules().then(setMods).catch(() => setMods([]));
    api.trainingSummary().then(setSum).catch(() => {});
    api.trainingLeaderboard().then(setBoard).catch(() => {});
  };
  useEffect(load, []);

  const remove = async (m: TrainingModule) => {
    const ok = await confirmDialog({
      title: "Delete training module",
      message: `Delete “${m.title}” and all of its enrollments? This can't be undone.`,
      confirmLabel: "Delete",
      danger: true,
    });
    if (!ok) return;
    try {
      await api.deleteModule(m.id);
      load();
    } catch (err) {
      notify(err instanceof ApiError ? err.message : "Delete failed", "error");
    }
  };

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Training</h1>
          <div className="page-sub">Awareness modules, quizzes, and completion tracking</div>
        </div>
        <button className="btn primary" onClick={() => setEditing(blankModule())}>+ New module</button>
      </div>

      {sum && (
        <div style={{ display: "flex", gap: 12, marginBottom: 18, flexWrap: "wrap" }}>
          <Stat label="Modules" value={sum.modules} />
          <Stat label="Enrollments" value={sum.enrollments} />
          <Stat label="Completed" value={sum.completed} accent="#166534" />
          <Stat label="Completion rate" value={`${sum.completion_rate}%`} accent="#4f46e5" />
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 18, alignItems: "start" }}>
        <div>
          {!mods ? (
            <p className="hint">Loading…</p>
          ) : mods.length === 0 ? (
            <div className="banner">No modules yet. Create one, or the starter library seeds on first run.</div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              {mods.map((m) => (
                <div key={m.id} className="card" style={{ margin: 0 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
                    <div style={{ minWidth: 0 }}>
                      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                        <strong style={{ fontSize: 15 }}>{m.title}</strong>
                        <span className="pill" style={{ background: "#eef2ff", color: DIFF_COLOR[m.difficulty] }}>
                          {m.difficulty}
                        </span>
                        {!m.is_published && <span className="pill" style={{ background: "#f1f5f9", color: "#64748b" }}>draft</span>}
                      </div>
                      <div className="hint" style={{ marginTop: 4 }}>{m.description}</div>
                      <div className="hint" style={{ marginTop: 6 }}>
                        {m.category} · {m.questions.length} question{m.questions.length === 1 ? "" : "s"} · ~{m.estimated_minutes} min ·{" "}
                        {m.points} pts · pass {m.pass_score}%
                      </div>
                      <div className="hint" style={{ marginTop: 6 }}>
                        👥 {m.enrolled} enrolled · ✓ {m.completed} completed
                      </div>
                    </div>
                    <div style={{ display: "flex", flexDirection: "column", gap: 6, flexShrink: 0 }}>
                      <button className="btn primary" onClick={() => setAssigning(m)}>Assign</button>
                      <button className="btn" onClick={() => setSending(m)} disabled={!m.enrolled} title={m.enrolled ? "Email the training link to enrolled people" : "Assign someone first"}>✉ Email links</button>
                      <button className="btn" onClick={() => setEditing(m)}>Edit</button>
                      <button className="btn" style={{ color: "#b91c1c" }} onClick={() => remove(m)}>Delete</button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="card" style={{ margin: 0 }}>
          <h2 style={{ margin: "0 0 12px", fontSize: 16 }}>🏆 Leaderboard</h2>
          {board.length === 0 ? (
            <p className="hint">No completions yet. Assign a module to get started.</p>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {board.map((r, i) => (
                <div key={r.email} style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <span style={{ width: 22, fontWeight: 700, color: i < 3 ? "#d97706" : "#94a3b8" }}>{i + 1}</span>
                  <span style={{ flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", fontSize: 13 }}>
                    {r.email}
                  </span>
                  <span style={{ fontWeight: 700, color: "#4f46e5" }}>{r.points}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <AutoEnrollCard mods={mods || []} />
      <Recommendations />

      {editing && (
        <ModuleModal
          initial={editing}
          onClose={() => setEditing(null)}
          onSaved={() => { setEditing(null); load(); }}
        />
      )}
      {assigning && (
        <AssignModal module={assigning} onClose={() => setAssigning(null)} onDone={() => { setAssigning(null); load(); }} />
      )}
      {sending && (
        <SendModal module={sending} onClose={() => setSending(null)} onDone={() => setSending(null)} />
      )}
    </>
  );
}

function Stat({ label, value, accent }: { label: string; value: number | string; accent?: string }) {
  return (
    <div className="card" style={{ flex: "1 1 130px", padding: "14px 16px", margin: 0 }}>
      <div style={{ fontSize: 26, fontWeight: 700, color: accent || "var(--text)" }}>{value}</div>
      <div className="hint">{label}</div>
    </div>
  );
}

function ModuleModal({
  initial, onClose, onSaved,
}: { initial: Partial<TrainingModule>; onClose: () => void; onSaved: () => void }) {
  const { notify } = useToast();
  const [f, setF] = useState<Partial<TrainingModule>>({ ...initial, questions: initial.questions?.map((q) => ({ ...q })) || [] });
  const [busy, setBusy] = useState(false);
  const set = (k: string, v: unknown) => setF((p) => ({ ...p, [k]: v }));
  const qs = f.questions || [];

  const setQ = (i: number, patch: Partial<QuizQuestion>) =>
    setF((p) => ({ ...p, questions: (p.questions || []).map((q, j) => (j === i ? { ...q, ...patch } : q)) }));
  const addQ = () => setF((p) => ({ ...p, questions: [...(p.questions || []), { prompt: "", options: ["", ""], correct_index: 0 }] }));
  const delQ = (i: number) => setF((p) => ({ ...p, questions: (p.questions || []).filter((_, j) => j !== i) }));

  const save = async () => {
    if (!f.title?.trim()) { notify("Title is required", "error"); return; }
    for (const q of qs) {
      if (!q.prompt.trim() || q.options.some((o) => !o.trim())) { notify("Fill in every question prompt and option", "error"); return; }
    }
    setBusy(true);
    const payload = {
      title: f.title, description: f.description || null, category: f.category || "General",
      difficulty: f.difficulty, content_html: f.content_html || "", video_url: f.video_url || null,
      estimated_minutes: f.estimated_minutes, pass_score: f.pass_score, points: f.points,
      is_published: f.is_published, questions: qs.map((q) => ({ prompt: q.prompt, options: q.options, correct_index: q.correct_index })),
    };
    try {
      if (f.id) await api.updateModule(f.id, payload);
      else await api.createModule(payload);
      notify("Module saved.", "ok");
      onSaved();
    } catch (err) {
      notify(err instanceof ApiError ? err.message : "Save failed", "error");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal title={f.id ? "Edit module" : "New module"} onClose={onClose} wide>
      <div>
          <div className="field">
            <label>Title</label>
            <input value={f.title || ""} onChange={(e) => set("title", e.target.value)} placeholder="Spot the Phish" />
          </div>
          <div className="field">
            <label>Description</label>
            <input value={f.description || ""} onChange={(e) => set("description", e.target.value)} />
          </div>
          <div className="row2">
            <div className="field">
              <label>Category</label>
              <input value={f.category || ""} onChange={(e) => set("category", e.target.value)} />
            </div>
            <div className="field">
              <label>Difficulty</label>
              <select value={f.difficulty} onChange={(e) => set("difficulty", e.target.value)}>
                {DIFFS.map((d) => <option key={d} value={d}>{d}</option>)}
              </select>
            </div>
          </div>
          <div className="row2">
            <div className="field">
              <label>Est. minutes</label>
              <input type="number" value={f.estimated_minutes} onChange={(e) => set("estimated_minutes", Number(e.target.value))} />
            </div>
            <div className="field">
              <label>Pass score (%)</label>
              <input type="number" value={f.pass_score} onChange={(e) => set("pass_score", Number(e.target.value))} />
            </div>
          </div>
          <div className="row2">
            <div className="field">
              <label>Points</label>
              <input type="number" value={f.points} onChange={(e) => set("points", Number(e.target.value))} />
            </div>
            <div className="field check" style={{ alignItems: "flex-end", paddingBottom: 10 }}>
              <input id="pub" type="checkbox" checked={!!f.is_published} onChange={(e) => set("is_published", e.target.checked)} />
              <label htmlFor="pub">Published</label>
            </div>
          </div>
          <div className="field">
            <label>Video URL (optional embed)</label>
            <input value={f.video_url || ""} onChange={(e) => set("video_url", e.target.value)} placeholder="https://…/embed/…" />
          </div>
          <div className="field">
            <label>Lesson content (HTML)</label>
            <textarea rows={8} value={f.content_html || ""} onChange={(e) => set("content_html", e.target.value)}
              style={{ fontFamily: "monospace", fontSize: 12 }} placeholder="<h2>…</h2><p>…</p>" />
          </div>

          <div style={{ borderTop: "1px solid var(--border, #e2e8f0)", paddingTop: 14, marginTop: 6 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
              <strong>Quiz questions</strong>
              <button className="btn" onClick={addQ}>+ Add question</button>
            </div>
            {qs.length === 0 && <p className="hint">No quiz — trainees just mark the lesson complete.</p>}
            {qs.map((q, i) => (
              <div key={i} style={{ border: "1px solid var(--border, #e2e8f0)", borderRadius: 10, padding: 12, marginBottom: 10 }}>
                <div style={{ display: "flex", gap: 8 }}>
                  <input style={{ flex: 1 }} placeholder={`Question ${i + 1}`} value={q.prompt}
                    onChange={(e) => setQ(i, { prompt: e.target.value })} />
                  <button className="btn" style={{ color: "#b91c1c" }} onClick={() => delQ(i)}>✕</button>
                </div>
                <div style={{ marginTop: 8, display: "flex", flexDirection: "column", gap: 6 }}>
                  {q.options.map((o, oi) => (
                    <div key={oi} style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <input type="radio" name={`correct-${i}`} checked={q.correct_index === oi}
                        onChange={() => setQ(i, { correct_index: oi })} title="Correct answer" />
                      <input style={{ flex: 1 }} placeholder={`Option ${oi + 1}`} value={o}
                        onChange={(e) => setQ(i, { options: q.options.map((x, j) => (j === oi ? e.target.value : x)) })} />
                      {q.options.length > 2 && (
                        <button className="btn" onClick={() => setQ(i, {
                          options: q.options.filter((_, j) => j !== oi),
                          correct_index: q.correct_index >= oi && q.correct_index > 0 ? q.correct_index - 1 : q.correct_index,
                        })}>✕</button>
                      )}
                    </div>
                  ))}
                  {q.options.length < 6 && (
                    <button className="linklike" style={{ background: "none", border: "none", color: "var(--accent)", cursor: "pointer", padding: 0, fontSize: 13, alignSelf: "flex-start" }}
                      onClick={() => setQ(i, { options: [...q.options, ""] })}>+ add option</button>
                  )}
                </div>
                <div className="hint" style={{ marginTop: 6 }}>● marks the correct answer</div>
              </div>
            ))}
          </div>
        <div className="btn-row" style={{ justifyContent: "flex-end", marginTop: 16 }}>
          <button className="btn" onClick={onClose}>Cancel</button>
          <button className="btn primary" onClick={save} disabled={busy}>{busy ? "Saving…" : "Save module"}</button>
        </div>
      </div>
    </Modal>
  );
}

const RISK_COLOR: Record<string, string> = { high: "#dc2626", medium: "#d97706", low: "#16a34a" };

function AutoEnrollCard({ mods }: { mods: TrainingModule[] }) {
  const { notify } = useToast();
  const [cfg, setCfg] = useState<AutoEnrollConfig | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.getAutoEnroll().then(setCfg).catch(() => setCfg(null));
  }, []);

  const save = async (next: AutoEnrollConfig) => {
    setBusy(true);
    try {
      setCfg(await api.updateAutoEnroll(next));
      notify("Auto-enroll settings saved.", "ok");
    } catch (err) {
      notify(err instanceof ApiError ? err.message : "Save failed", "error");
    } finally {
      setBusy(false);
    }
  };

  if (!cfg) return null;
  return (
    <div className="card" style={{ marginTop: 20 }}>
      <h2 style={{ margin: "0 0 4px", fontSize: 16 }}>⚡ Just-in-time auto-enrollment</h2>
      <p className="hint" style={{ marginBottom: 14 }}>
        When someone clicks or submits in a simulation, automatically enroll them in training — the teachable moment,
        while the mistake is fresh. In <strong>adaptive</strong> mode the module's difficulty is chosen from their
        behaviour (credential submitters &amp; repeat clickers get foundational material).
      </p>
      <div className="field check">
        <input id="ae" type="checkbox" checked={cfg.enabled} disabled={busy}
          onChange={(e) => save({ ...cfg, enabled: e.target.checked })} />
        <label htmlFor="ae">Enable auto-enrollment on failed simulations</label>
      </div>
      <div className="row2">
        <div className="field">
          <label>Mode</label>
          <select value={cfg.mode} disabled={busy || !cfg.enabled}
            onChange={(e) => save({ ...cfg, mode: e.target.value as "adaptive" | "fixed" })}>
            <option value="adaptive">Adaptive (difficulty by risk)</option>
            <option value="fixed">Fixed module</option>
          </select>
        </div>
        {cfg.mode === "fixed" && (
          <div className="field">
            <label>Module</label>
            <select value={cfg.module_id ?? ""} disabled={busy || !cfg.enabled}
              onChange={(e) => save({ ...cfg, module_id: e.target.value ? Number(e.target.value) : null })}>
              <option value="">— pick —</option>
              {mods.map((m) => <option key={m.id} value={m.id}>{m.title}</option>)}
            </select>
          </div>
        )}
      </div>
    </div>
  );
}

function Recommendations() {
  const [recs, setRecs] = useState<RecommendationRow[] | null>(null);
  useEffect(() => {
    api.trainingRecommendations().then(setRecs).catch(() => setRecs([]));
  }, []);

  if (!recs || recs.length === 0) return null;
  return (
    <div className="card" style={{ marginTop: 20 }}>
      <h2 style={{ margin: "0 0 4px", fontSize: 16 }}>🎯 Adaptive recommendations</h2>
      <p className="hint" style={{ marginBottom: 14 }}>
        Suggested next-simulation difficulty per person, from their behaviour across campaigns. Savvy users earn harder
        lures; those who slip up get gentler ones plus targeted training.
      </p>
      <div style={{ overflowX: "auto" }}>
        <table className="table" style={{ width: "100%" }}>
          <thead>
            <tr>
              <th style={{ textAlign: "left" }}>Recipient</th>
              <th>Risk</th>
              <th>Failed / targeted</th>
              <th>Next simulation</th>
              <th>Training</th>
            </tr>
          </thead>
          <tbody>
            {recs.map((r) => (
              <tr key={r.email}>
                <td style={{ textAlign: "left" }}>{r.email}</td>
                <td style={{ textAlign: "center" }}>
                  <span className="pill" style={{ background: "var(--bg-panel)", color: RISK_COLOR[r.risk] }}>{r.risk}</span>
                </td>
                <td style={{ textAlign: "center" }}>{r.failed} / {r.targeted}</td>
                <td style={{ textAlign: "center" }}>{r.next_sim_difficulty}</td>
                <td style={{ textAlign: "center" }}>{r.recommended_training_difficulty}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function AssignModal({
  module, onClose, onDone, defaultCampaignId, defaultOutcome,
}: {
  module: TrainingModule; onClose: () => void; onDone: () => void;
  defaultCampaignId?: number; defaultOutcome?: string;
}) {
  const { notify } = useToast();
  const [groups, setGroups] = useState<GroupSummary[]>([]);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [groupId, setGroupId] = useState<number | "">("");
  const [campaignId, setCampaignId] = useState<number | "">(defaultCampaignId ?? "");
  const [outcome, setOutcome] = useState(defaultOutcome ?? "clicked");
  const [emails, setEmails] = useState("");
  const [preview, setPreview] = useState<{ count: number; total: number } | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.listGroups().then(setGroups).catch(() => setGroups([]));
    api.listCampaigns().then(setCampaigns).catch(() => setCampaigns([]));
  }, []);

  // Live audience count for the "train the people who failed" flow.
  useEffect(() => {
    if (campaignId === "") { setPreview(null); return; }
    let alive = true;
    api.trainingAudience({ campaign_id: Number(campaignId), outcome })
      .then((r) => { if (alive) setPreview(r); })
      .catch(() => { if (alive) setPreview(null); });
    return () => { alive = false; };
  }, [campaignId, outcome]);

  const submit = async () => {
    const list = emails.split(/[\s,;]+/).map((e) => e.trim()).filter((e) => e.includes("@"));
    if (list.length === 0 && groupId === "" && campaignId === "") {
      notify("Pick a campaign, a group, or paste emails", "error"); return;
    }
    setBusy(true);
    try {
      const r = await api.assignModule(module.id, {
        emails: list,
        group_id: groupId === "" ? null : Number(groupId),
        campaign_id: campaignId === "" ? null : Number(campaignId),
        outcome,
      });
      notify(r.detail, "ok");
      onDone();
    } catch (err) {
      notify(err instanceof ApiError ? err.message : "Assign failed", "error");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal title={`Assign “${module.title}”`} onClose={onClose}>
      <div>
        <div className="field">
          <label>🎯 From a campaign <span className="hint">— train the people who failed</span></label>
          <select value={campaignId} onChange={(e) => setCampaignId(e.target.value === "" ? "" : Number(e.target.value))}>
            <option value="">— none —</option>
            {campaigns.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </div>
        {campaignId !== "" && (
          <div className="field">
            <label>Who from that campaign</label>
            <select value={outcome} onChange={(e) => setOutcome(e.target.value)}>
              {TRAINING_OUTCOMES.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
            {preview && (
              <span className="hint" style={{ marginTop: 6 }}>
                This will enroll <strong style={{ color: "var(--accent)" }}>{preview.count}</strong> of {preview.total} recipient(s).
              </span>
            )}
          </div>
        )}
        <div className="row2">
          <div className="field">
            <label>Or a group</label>
            <select value={groupId} onChange={(e) => setGroupId(e.target.value === "" ? "" : Number(e.target.value))}>
              <option value="">— none —</option>
              {groups.map((g) => <option key={g.id} value={g.id}>{g.name} ({g.target_count})</option>)}
            </select>
          </div>
          <div className="field">
            <label>Or paste emails</label>
            <textarea rows={2} value={emails} onChange={(e) => setEmails(e.target.value)}
              placeholder="alice@corp.com, bob@corp.com" />
          </div>
        </div>
        <div className="banner" style={{ margin: 0 }}>
          Each person gets a unique training link. Already-enrolled (incomplete) people are skipped. Sources combine
          (deduped). After assigning, use <strong>✉ Email links</strong> to send them.
        </div>
        <div className="btn-row" style={{ justifyContent: "flex-end", marginTop: 16 }}>
          <button className="btn" onClick={onClose}>Cancel</button>
          <button className="btn primary" onClick={submit} disabled={busy}>{busy ? "Assigning…" : "Assign"}</button>
        </div>
      </div>
    </Modal>
  );
}

function SendModal({ module, onClose, onDone }: { module: TrainingModule; onClose: () => void; onDone: () => void }) {
  const { notify } = useToast();
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [profileId, setProfileId] = useState<number | "">("");
  const [onlyPending, setOnlyPending] = useState(true);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.listProfiles().then((ps) => { setProfiles(ps); if (ps[0]) setProfileId(ps[0].id); }).catch(() => setProfiles([]));
  }, []);

  const submit = async () => {
    if (profileId === "") { notify("Pick a sending profile", "error"); return; }
    setBusy(true);
    try {
      const r = await api.sendTrainingInvites(module.id, { profile_id: Number(profileId), only_pending: onlyPending });
      notify(r.detail, "ok");
      onDone();
    } catch (err) {
      notify(err instanceof ApiError ? err.message : "Send failed", "error");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal title={`Email training links — “${module.title}”`} onClose={onClose}>
      <p className="hint" style={{ marginBottom: 14 }}>
        Sends each enrolled person their <strong>unique</strong> training link by email, through a sending profile
        (delivery goes through the durable queue). You can re-send anytime.
      </p>
      {profiles.length === 0 ? (
        <div className="banner" style={{ margin: 0 }}>No sending profiles yet — add one under <strong>Sending Profiles</strong> first.</div>
      ) : (
        <>
          <div className="field">
            <label>Sending profile</label>
            <select value={profileId} onChange={(e) => setProfileId(e.target.value === "" ? "" : Number(e.target.value))}>
              {profiles.map((p) => <option key={p.id} value={p.id}>{p.name} — {p.from_address}</option>)}
            </select>
          </div>
          <label className="field check" style={{ cursor: "pointer" }}>
            <input type="checkbox" checked={onlyPending} onChange={(e) => setOnlyPending(e.target.checked)} />
            <span>Only those who haven't completed it yet</span>
          </label>
          <div className="btn-row" style={{ justifyContent: "flex-end", marginTop: 12 }}>
            <button className="btn" onClick={onClose}>Cancel</button>
            <button className="btn primary" onClick={submit} disabled={busy}>{busy ? "Queuing…" : "Send emails"}</button>
          </div>
        </>
      )}
    </Modal>
  );
}
