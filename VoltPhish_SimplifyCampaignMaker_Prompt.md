# VoltPhish — Make the Campaign Maker Simple & User-Friendly

A ready-to-use prompt for Claude (Claude Code / Cowork). It invokes the **`ui-ux-design`** skill and focuses on one goal: the "New campaign" flow currently feels heavy/complex — make it feel effortless for a normal user, without losing any power for advanced users.

**How to run:** point Claude at the repo (or the campaign-modal component), paste the prompt below, review the diff, iterate.

---

## The prompt

```
Use your ui-ux-design skill. Act as a senior product designer improving VoltPhish — a
self-hosted phishing-simulation & security-awareness platform with a dark-first React UI.

PROBLEM: The "New campaign" creator feels complicated. It's a 5-step wizard (Audience →
Lure → Delivery → Remediation → Review) that asks the user about target groups, a
never-phish exclusion list, sending profile, landing page, phishing URL (public tunnel /
custom), auto-enrol-on-failure + module, schedule + drip + timezone, and an authorization
attestation — all before a first campaign can go out. For a normal/first-time user this is
too much cognitive load and too many decisions.

GOAL: Make creating a campaign feel effortless. A new user should be able to launch a
sensible test campaign in as few decisions as possible, while power users keep full control.
Reduce perceived and actual complexity — do NOT remove capability.

Design principles to apply:
1. QUICK-LAUNCH DEFAULT PATH. Make the primary flow a short, smart, single-screen (or 2-step
   max) "Quick launch": pick who to phish + pick a lure, and everything else uses sensible
   defaults (best sending profile, public URL auto-selected, built-in awareness landing,
   launch now, auto-enrol off). The user should reach a launchable state having touched only
   2–3 controls.
2. PROGRESSIVE DISCLOSURE. Move every advanced/rare option — exclusion list, drip/schedule,
   custom URL, auto-enrol rules, authorization reference — behind a clearly labelled
   "Advanced options" area that is COLLAPSED by default. The default view shows only what
   most users need.
3. SMART DEFAULTS + RECOMMENDATIONS. Pre-select the safest, most common choices and label
   them "Recommended". If a public tunnel URL is available, default to it and explain in one
   line. Never present an empty required field the user must decode.
4. PRESETS / STARTING POINTS. Offer 2–3 one-click starting points (e.g. "Quick test to
   myself", "Password-reset lure", "MS365 sign-in lure") that pre-fill template + landing +
   settings, so users start from something good instead of a blank form.
5. PLAIN LANGUAGE. Rewrite labels and helper text in friendly, jargon-free language with
   short inline hints/tooltips. Explain WHY each choice matters in one sentence, only where
   needed.
6. LIVE PREVIEW + CLEAR SUMMARY. Show a small preview of the email/landing the recipient
   will see, and a plain-English one-line summary of what's about to happen ("Send the
   'Password expiry' email to 12 people now, from your public link").
7. KEEP IT SAFE. The "I'm authorized to run this simulation" attestation and the final
   confirm before the irreversible send must stay — but make them feel like a natural last
   step, not a barrier. Keep the recipient dedupe + exclusion live count.
8. DUAL MODE. Keep the existing full wizard available as an "Advanced / full control" mode
   (a toggle or link), so nothing is lost for power users. Quick-launch is just the default.

Target: a first-time user can create and launch a reasonable test campaign in under ~4
interactions and ~15 seconds, with zero confusion about required vs optional fields.

Deliverables:
- The redesigned Quick-launch flow (wireframes / component structure) + how it collapses the
  advanced options.
- Rewritten microcopy for the main fields.
- Component + interaction specs, using the existing design tokens (dark-first + light mode),
  fully keyboard- and screen-reader-accessible (role=dialog, focus management, labelled
  controls).
- A short before/after rationale explaining how each change reduces complexity.

Constraints: reuse the existing design system/tokens; do NOT remove any existing capability
(only reorganize + default + hide behind Advanced); do NOT change backend behavior or field
names it submits; keep the authorization attestation and dedupe/exclusion logic intact.
```

---

### Optional add-ons you can tack on
- *"Also add a first-run empty state on the Campaigns page with a single 'Launch your first campaign' CTA that opens Quick-launch."*
- *"Add a 'Send test to myself' shortcut so users can preview the whole flow safely before targeting real people."*
- *"Run an axe/Lighthouse accessibility pass on the new flow and fix any issues."*
