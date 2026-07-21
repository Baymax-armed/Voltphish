# 🚀 VoltPhish — Launch kit

Copy-paste material to launch VoltPhish. Post to a few communities on the **same day**,
reply to every comment fast, and the momentum compounds. Don't buy stars or spam — it
backfires. Real traction comes from the right communities + good screenshots.

---

## 0. Do these first (10 min, biggest impact)

1. **Repo "About" (gear icon on the repo page):**
   - **Description:** `Open-source, self-hosted phishing simulation & security-awareness platform — the free alternative to paid enterprise tools. Email · QR · training LMS · report button · human-risk analytics. One Docker command.`
   - **Website:** (your live demo or the artifact landing page link)
   - **Topics:** `phishing` `phishing-simulation` `security-awareness` `security-awareness-training` `cybersecurity` `blue-team` `self-hosted` `fastapi` `react` `docker` `infosec` `soc` `open-source`

2. **Add screenshots / a demo GIF to the top of the README** (see shot list below). A repo
   with a demo GIF gets *dramatically* more stars than one without. This is the #1 lever.

3. **Pin the repo** on your GitHub profile.

---

## 1. Screenshot / GIF shot list (capture from the running app)

Run `docker compose up`, log in, and grab these (use ShareX / ScreenToGif / Kap):
- **Hero GIF (most important):** create a campaign → launch → watch the live dashboard funnel light up (open → click → submit → reported). 8–15s loop.
- Dashboard: funnel + Human Risk Score + geo map + attack-surface/VIP.
- Template gallery (the phishing email previews).
- Training module + quiz (the trainee `/train` page).
- Reported-emails triage queue + the "Install Report-Phish button" card.
- Settings: AI provider + SSO + benchmark cards.

Save under `docs/screenshots/` and reference them in the README.

---

## 2. Show HN (news.ycombinator.com/submit)

> **Title:** Show HN: VoltPhish – Open-source, self-hosted phishing simulation platform

> **URL:** https://github.com/Baymax-armed/Voltphish

> **First comment (post immediately after):**
>
> Hi HN. VoltPhish is a self-hosted phishing-simulation & security-awareness tool — think
> an open-source take on the paid enterprise tools — with the whole awareness loop built
> in (most open-source options are unmaintained).
>
> It runs as one Docker container (React admin + FastAPI backend + tracking server). Beyond
> "who clicked," it does the parts a real awareness program needs: a one-click Report-Phish
> button (Outlook add-in + Gmail script), a training LMS that auto-enrolls anyone who fails,
> human-risk scoring, and email/QR/calendar lures. Secure-by-default: argon2id, AES-GCM
> column encryption, CSRF, SSRF guard, TOTP 2FA, OIDC SSO, RBAC. Optional Postgres + Redis
> for scaling.
>
> Honest caveats: it's young. It has ~60 tests and I ran a security review (and fixed a
> privilege-escalation bug I'd introduced) — but it hasn't had an independent pentest, and
> the authz model is single-tenant today. I'd use it for a small org/lab now; I'd want an
> external review before pointing it at thousands of employees' data. Feedback welcome.
>
> `docker compose up --build` → http://localhost:8080

*(HN tip: be technical and humble, reply to every comment within the first 2 hours.)*

---

## 3. r/selfhosted

> **Title:** I built VoltPhish — a self-hosted, open-source phishing-simulation & security-awareness platform (self-hosted, open-source)
>
> **Body:**
> Ran one `docker compose up` and you get a full security-awareness platform: send simulated
> phishing (email, QR, calendar), a one-click Report-Phish button for employees, a built-in
> training LMS that auto-enrolls people who fail, and a dashboard with a human-risk score +
> geo map. All self-hosted — the "who clicked" data stays on your box, never a vendor's.
>
> MIT licensed. React + FastAPI, SQLite by default (Postgres optional). Passwords submitted
> to fake login pages are **never** stored — it's built as a trainer, not a credential grabber.
>
> Repo: https://github.com/Baymax-armed/Voltphish — [screenshots/GIF]
>
> It's early and I'd love feedback from anyone running awareness programs.

*(Reddit needs images to do well — attach the dashboard GIF.)*

---

## 4. r/cybersecurity / r/blueteam / r/AskNetsec

> **Title:** Open-source alternative to paid phishing-simulation tools + awareness training (self-hosted)
>
> **Body:**
> Built VoltPhish for teams that want to run phishing sims + awareness training without paying
> per-seat for enterprise (paid) tools. It closes the loop: attack → report → train → measure.
> Native Outlook/Gmail Report-Phish button, just-in-time training auto-enrollment, human-risk
> scoring, VAP-style attack surface, deliverability allowlist generator, SSO + admin 2FA + RBAC.
>
> Self-hosted, MIT, one Docker container. Would genuinely value blue-team feedback on the
> report-button flow and the risk model. https://github.com/Baymax-armed/Voltphish

---

## 5. Product Hunt

> **Tagline:** The open-source, self-hosted alternative to paid enterprise tools
> **Description:** VoltPhish is a phishing-simulation & security-awareness platform you run in
> one Docker container. Email/QR/calendar lures, a one-click Report-Phish button, a training
> LMS that auto-enrolls anyone who fails, and human-risk analytics — all self-hosted, MIT-licensed.
> **Topics:** Security, Developer Tools, Open Source, SaaS alternatives

---

## 6. X / Twitter thread

> 1/ I built VoltPhish — an open-source, self-hosted phishing-simulation & security-awareness
> platform. The free alternative to paid enterprise tools. One `docker compose up`. 🧵👇 [GIF]
>
> 2/ Most OSS phishing tools stop at "who clicked." VoltPhish runs the whole program:
> attack → report → train → measure.
>
> 3/ ✅ Email · QR · calendar lures
> ✅ One-click Report-Phish button (Outlook + Gmail)
> ✅ Training LMS that auto-enrolls anyone who fails
> ✅ Human-risk score, geo map, VAP view
>
> 4/ Secure-by-default: argon2id, AES-GCM, CSRF, SSRF guard, TOTP 2FA, OIDC SSO, RBAC.
> Passwords typed into fake logins are never stored — it's a trainer, not a grabber.
>
> 5/ MIT. Self-hosted so employee data never leaves your box. Star it / try it 👇
> https://github.com/Baymax-armed/Voltphish

> **Hashtags:** #infosec #cybersecurity #phishing #opensource #selfhosted #blueteam

---

## 7. LinkedIn

> After seeing how much teams pay per-seat for security-awareness training, I built and
> open-sourced **VoltPhish** — a self-hosted phishing-simulation & awareness platform.
>
> Run realistic simulations (email, QR, calendar), give employees a one-click Report-Phish
> button, auto-enroll anyone who fails into short training, and measure human risk — all in
> one Docker container, with your data staying on your own infrastructure.
>
> MIT-licensed and free. Built for security teams who want enterprise-grade outcomes without the
> enterprise bill. Feedback from security & awareness folks very welcome 👇
> https://github.com/Baymax-armed/Voltphish
>
> #cybersecurity #infosec #securityawareness #opensource

---

## 8. Where else

- **awesome-selfhosted** — open a PR adding VoltPhish under "Security".
- **awesome-security / awesome-cybersecurity-blueteam** lists — PRs.
- **r/msp, r/sysadmin** — the MSP/IT-admin angle.
- **Hacker News "Show HN" + a dev.to / Hashnode writeup** ("Why I built an open-source, self-hosted awareness platform").
- **Mastodon (infosec.exchange)** — the security community is active there.

Post 2–3 of these on day one, space the rest over the week, and reply to every comment.
