---
tags:
  - '#exec'
  - '#live-pull-verification-sweep'
date: '2026-07-10'
modified: '2026-07-10'
body_hash: 'sha256:0cb246cf5f281a7865a131b0a9e5271325517cd3e3a422967e670090635df740'
step_id: 'S22'
related:
  - "[[2026-06-12-live-pull-verification-sweep-plan]]"
  - "[[2026-06-12-live-pull-verification-sweep-live-auth-blocker-audit]]"
---

# Exercise justificante CLI commands for pull, list, view, and reconcile-from-persisted evidence

## Scope

- `src/aeat/entrypoints/cli/_app_live_justificante_cli.py src/aeat/entrypoints/cli/tests/test_live_justificante_verbs.py`

## Description

- Reconciliation closure for the justificante CLI command surface. Evidence is
  the offline justificante-verb suite green at HEAD, the backend reconcile /
  refusal suites (real Modelo 130 PDF fixture) green at HEAD, and the live
  authenticated justificante-list positive already captured in the read sweep.

## Outcome

The justificante CLI is proven to expose `pull`, `list`, `view`, and
reconcile-from-persisted evidence with backend evidence required before success.

Verification (re-run at HEAD 2026-07-10):

- `uv run --no-sync pytest src/aeat/entrypoints/cli/tests/test_live_justificante_verbs.py -q`
  passed (batched run: 34 passed with the notifications/portals/iva/borrador
  suites).
- Backend reconcile / stamp / refusal coverage green at HEAD:
  `uv run --no-sync pytest src/aeat/application/live/tests/test_justificante_capture.py src/aeat/application/live/tests/test_justificante_capture_orchestrator.py src/aeat/application/live/tests/test_justificante_capture_resolution.py src/aeat/application/live/tests/test_justificante_capture_stamp.py src/aeat/application/live/tests/test_justificante_reconcile_from_persisted.py -q`
  passed (part of the 67-passed live-backend batch); these exercise the real
  Modelo 130 justificante PDF, mismatch refusal, and no-temp-file leak.
- Live positive already on record in the live-auth read sweep exec:
  `app live justificante list` returned `count=0`.

## Notes

- No positive `justificante pull` was live-exercised because the authenticated
  account has zero filed declarations, so there is no filed receipt to target;
  the download / persist / stamp / reconcile / refusal contract is proven
  offline against the real receipt fixture. A positive live justificante pull
  depends on an account with a filed declaration and is carried forward with
  the operator manual sweep (S26).
