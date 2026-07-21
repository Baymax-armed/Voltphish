# VoltPhish — UI/UX Improvement Prompts

Ready-to-use prompts for Claude (Claude Code / Cowork). Each one invokes the **`ui-ux-design`** skill and is written from a design-lead perspective, scoped to VoltPhish (a dark-first React admin UI for a self-hosted phishing-simulation & security-awareness platform).

**Suggested order:** run **Prompt 1** first (it establishes the design system everything else builds on), then 2, 3, 4 in any order. Each says "don't change functionality — only styling/structure," so they're safe to run incrementally.

---

## Prompt 1 — Design system foundation (run this first)

```
Use your ui-ux-design skill. Act as the design lead for VoltPhish — a self-hosted
phishing-simulation & security-awareness platform with a dark-first React admin UI.

Audit the current UI and establish one cohesive design system, then apply it across
the whole app:
- Color tokens: backgrounds, surfaces, borders, text (primary/secondary/muted), and
  semantic colors (success / warning / danger / info) PLUS the risk tiers
  (low / medium / high) as a single reusable color language used everywhere
  (People view, VIP table, benchmark, badges). Every token must pass WCAG AA
  (4.5:1 body text, 3:1 large/UI) in BOTH dark and light mode. Specifically fix the
  low-contrast grey helper text.
- Type scale, an 8px spacing system, radius, and elevation/shadow tokens.
- Full interaction states (default / hover / focus-visible / active / disabled /
  loading) for buttons, inputs, selects, the toggle-chips used for group selection,
  tables, modals, toasts, and badges.

Deliver: tokens as CSS variables + a one-page component reference sheet, then refactor
the components to use them. Keep the VoltPhish brand personality (electric-blue,
angler-fish energy). Change styling/structure only — do NOT alter functionality.
Briefly explain each major decision.
```

---

## Prompt 2 — Dashboard + data-viz redesign

```
Use your ui-ux-design skill and its data-visualization guidance. Redesign the VoltPhish
dashboard as a clean security-program analytics view.

Current cards (keep all the data, reorganize): KPI tiles (campaigns / active / recipients
/ templates), engagement funnel (sent → opened → clicked → submitted → reported), success
rings, campaign status, "at-risk users", "where clicks came from" (geo), industry
benchmark (you vs baseline), and "attack surface & VIPs".

Goals:
- Clear visual hierarchy: a top KPI row → primary funnel + trend-over-time → people/risk
  → geo → benchmark. Group related cards, kill visual noise.
- ONE consistent, color-blind-safe chart palette (categorical + sequential) that works in
  dark AND light, with consistent axis / legend / tooltip / and a proper "not enough data
  yet" empty state.
- Recommend the correct chart type per metric (funnel, trend, geo, comparison) instead of
  generic bars.
- Reuse the low/medium/high risk color language from the design system.

Deliver: a responsive grid layout, per-card component specs, and the chart palette tokens.
Dark-first, accessible. Don't invent data — design the empty and populated states both.
```

---

## Prompt 3 — Campaign builder as a guided flow

```
Use your ui-ux-design skill. Redesign VoltPhish's "New campaign" modal. It currently crams
everything into one long modal: email template, multi-group targeting, never-phish
exclusion list (with a live deduped recipient count), sending profile, landing page,
phishing URL (public Cloudflare-tunnel / this-server / custom), auto-enroll-on-failure
+ module picker, schedule + drip, timezone label, and an authorization attestation.

Turn it into a calm, guided multi-step flow with progressive disclosure:
  1) Audience  2) Lure (template + landing)  3) Delivery (profile + public URL + schedule)
  4) Remediation (auto-enroll rule)  5) Review & launch
- A persistent live summary rail: recipient count after dedup + exclusion, chosen
  template/landing/URL, and the auto-enroll rule.
- Inline validation, and the irreversible launch gated behind the final Review step
  (put the "I'm authorized" attestation there).
- Design the reusable toggle-chip multiselect for target vs exclude groups, plus
  empty / loading / error states.
- Keep it fast for power users: offer a compact single-view toggle too.

Deliver: the flow + wireframes + component specs. Dark-first, keyboard- and
screen-reader-friendly. Do NOT remove any existing field — only reorganize and clarify.
```

---

## Prompt 4 — Interaction & accessibility polish (the finishing pass)

```
Use your ui-ux-design skill. Do an interaction-quality and accessibility polish pass across
the whole VoltPhish app, building on the established design system. Focus on the details
that make it feel premium and inclusive — not new features.

Cover:
- Loading states: skeleton rows for every data table (Campaigns, People, Templates,
  Webhooks, Users) and spinners/disabled+busy states for async buttons (Save, Verify,
  Generate allowlist, Launch) so nothing flashes empty.
- Feedback consistency: every mutating action (save, send test, assign training, gallery
  add, webhook test) shows a success/failure toast with a consistent position, timing,
  icon, and color from the semantic tokens.
- Destructive-action safety: confirm dialogs (or undo) on all deletes and "Revoke API key",
  with the dangerous button clearly styled and never the default focus target.
- Live data: auto-refresh campaign results while a campaign is "in progress" (poll or
  websocket) with a subtle "updated Xs ago" indicator, instead of a manual Refresh.
- Empty states: give each empty list a friendly illustration + a primary CTA inside the
  card ("Create your first campaign").
- Accessibility to WCAG 2.1 AA: visible focus rings, full keyboard support (Esc closes
  modals, Enter submits, arrow keys on the group toggle-chips), correct ARIA roles/labels
  on modals, tables, toasts, and the risk badges, and a run of axe/Lighthouse with the
  issues fixed.
- Motion: subtle, consistent transitions (modal open, toast in/out, row hover) with a
  prefers-reduced-motion fallback.

Deliver: a prioritized checklist of what you changed, the shared components you added
(Skeleton, Toast, ConfirmDialog, EmptyState), and before/after notes. Dark-first, and do
NOT change any functionality — only interaction, feedback, and a11y.
```

---

### Tips for running these
- Point Claude at the actual repo/files first (or paste the relevant component) so it edits real code, not mockups.
- Run one prompt, review the diff, then the next — the design-system prompt should land before the others so tokens exist to reuse.
- Ask for a short rationale with each so you can review the *why*, not just the *what*.
