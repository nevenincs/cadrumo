---
tags:
  - '#exec'
  - '#live-pull-verification-sweep'
date: '2026-07-10'
modified: '2026-07-10'
body_hash: 'sha256:4d6847a7bf20d5a36e5d0392fec10e095828ac32ea647cd8981117c9949838fb'
step_id: 'S13'
related:
  - "[[2026-06-12-live-pull-verification-sweep-plan]]"
  - "[[2026-06-12-live-pull-verification-sweep-live-auth-blocker-audit]]"
---

# Prove notifications pull fetches authenticated notification rows with read-only parsing and no acknowledgement or mutation path

## Scope

- `src/aeat/application/live src/aeat/adapters/outbound/aeat/sede src/aeat/entrypoints/cli/_app_live_notifications_cli.py`

## Description

- Reconciliation closure for the notifications backend pull facade. Evidence is
  the offline real-behavior notifications backend suite at HEAD plus the live
  authenticated positive pull already recorded in the live-auth read sweep.
- Confirmed the notifications facade is a read-only parse path: no
  acknowledgement, dismissal, or mutation verb is reachable; the CLI exposes
  only `app live notifications pull`.

## Outcome

Backend notifications pull is proven read-only with real-behavior tests green at
HEAD and a live authenticated positive already captured.

Verification (re-run at HEAD 2026-07-10):

- `uv run --no-sync pytest src/aeat/application/live/tests/test_notifications.py -q`
  passed as part of the batched live-backend run (67 passed across
  justificante/notifications/expedientes suites).
- Live positive already on record in the live-auth read sweep exec
  (`...-live-auth-read-sweep`): `app live notifications pull` returned
  `row_count=1` with a persisted encrypted snapshot and the pulled row projected
  into the overview calendar as an `aeat_sede_notifications` message event. Raw
  taxpayer values were redacted in that evidence; only aggregate shape is cited.

## Notes

- The single live positive was a real authenticated pull; no acknowledgement or
  mutation path was exercised or exists. This row is closed on read-only backend
  proof plus the one live positive; broader multi-row live coverage is not
  required by the row and remains a matter for the operator manual sweep (S26,
  carried forward).
