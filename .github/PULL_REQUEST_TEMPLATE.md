<!--
Thanks for contributing to VoltPhish! Keep PRs focused and describe the "why".
Do NOT include secrets, .env, voltphish.db, or real recipient data in the diff.
-->

## What & why

<!-- What does this change do, and what problem does it solve? Link issues. -->

Closes #

## Type of change

- [ ] 🐛 Bug fix
- [ ] ✨ Feature
- [ ] 🎨 UI / UX
- [ ] ♻️ Refactor / chore
- [ ] 📝 Docs

## How was it tested?

<!-- Commands run, manual steps, screenshots for UI. -->

- [ ] `pytest` (backend) passes
- [ ] `tsc --noEmit` (frontend) is clean
- [ ] Built & ran via Docker and verified the change in the app

## Checklist

- [ ] No secrets, API keys, `.env`, or `*.db` in the diff
- [ ] New/changed inputs are validated; new DB queries are parameterized
- [ ] New endpoints have auth + authorization checks; errors don't leak internals
- [ ] Added/updated tests for the change (happy path + at least one abuse case)
- [ ] Docs / README / SECURITY updated if behavior or trust boundary changed
- [ ] Change keeps VoltPhish's **authorized, defensive** scope (no help for
      unauthorized attacks, credential cloning, MFA bypass, or evasion)
