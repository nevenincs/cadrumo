---
tags:
  - '#exec'
  - '#live-pull-verification-sweep'
date: '2026-07-10'
modified: '2026-07-10'
body_hash: 'sha256:7740f6b0dbbb402def3436f8d12e06d969081a10192c163e47b863eb9243601b'
step_id: 'S21'
related:
  - "[[2026-06-12-live-pull-verification-sweep-plan]]"
  - "[[2026-06-12-live-pull-verification-sweep-live-auth-blocker-audit]]"
---

# Exercise notifications CLI commands with authenticated results and prove no acknowledgement, dismissal, or remote mutation is reachable

## Scope

- `src/aeat/entrypoints/cli/_app_live_notifications_cli.py src/aeat/entrypoints/cli/tests/test_live_notifications_verbs.py`

## Description

- Reconciliation closure for the notifications CLI command surface. Evidence is
  the offline notifications-verb suite green at HEAD plus the live authenticated
  positive pull already captured in the live-auth read sweep.

## Outcome

The notifications CLI is proven read-only: it pulls authenticated rows and
exposes no acknowledgement, dismissal, or remote-mutation verb.

Verification (re-run at HEAD 2026-07-10):

- `uv run --no-sync pytest src/aeat/entrypoints/cli/tests/test_live_notifications_verbs.py -q`
  passed (batched run: 34 passed with the justificante/portals/iva/borrador
  suites); the command tree exposes only `app live notifications pull`.
- Live positive already on record in the live-auth read sweep exec:
  `app live notifications pull` returned `row_count=1` with a persisted
  encrypted snapshot; the row projected into the overview calendar as an
  `aeat_sede_notifications` message event. Raw values redacted; shape only.

## Notes

- The authenticated positive was a real read pull; no acknowledgement or
  mutation path exists or was exercised. Broader multi-row live coverage is a
  matter for the operator manual sweep (S26), carried forward.
