---
tags:
  - '#exec'
  - '#docs-lifecycle-tutorials'
date: '2026-07-13'
modified: '2026-07-13'
body_hash: 'sha256:1792cf6bcb7765b907d51297f1861815c8264015d49b5298e8152f3af23e7622'
step_id: 'S05'
related:
  - "[[2026-07-13-docs-lifecycle-tutorials-plan]]"
---

# Retire read-live-aeat-data.md, redistributing its live-pull content to check-aeat-notifications.md, censo-update.md, and reconcile.md

## Scope

- `sweep inbound links`
- `docs/how-to/read-live-aeat-data.md docs/how-to/check-aeat-notifications.md docs/how-to/censo-update.md docs/how-to/reconcile.md`

## Description

- Add a "How a live read works" section to
  `docs/how-to/check-aeat-notifications.md` absorbing the retired page's
  durable signal: the uniform read-only pull-to-encrypted-local-copy pattern,
  the apply-nothing-automatically rule, the boundary cross-link, the
  auth-preflight refusal explanation (Cl@ve message vs real cause), and the
  `AEAT_LIVE_TESTS_ENABLED` developer-setting note; add the "This page covers
  the ..." opening.
- Point the censo and justificante surfaces at their own guides
  (`censo-update.md`, `reconcile.md#pull-and-store-the-justificante`) instead
  of re-listing their commands.
- Sweep inbound references: the how-to index grid card and toctree entry
  removed, `runbooks/RB-002-live-read-refused.md` retargeted to
  `check-aeat-notifications.md`.
- Delete `docs/how-to/read-live-aeat-data.md` via `git rm`.

## Outcome

The thin live-read index page is retired; its unique content lives on the
page that actually lists the live commands. Grep confirms zero remaining
`read-live-aeat-data` references outside build artifacts.

## Notes

`censo-update.md` needed no addition: the review-then-apply pattern the
retired page described is already that guide's core workflow.
