---
tags:
  - '#exec'
  - '#live-pull-verification-sweep'
date: '2026-07-10'
modified: '2026-07-10'
body_hash: 'sha256:8484baf3d94029e8617c103305a8fc53e34e35637b96db529aced23e0610a373'
step_id: 'S20'
related:
  - "[[2026-06-12-live-pull-verification-sweep-plan]]"
  - "[[2026-06-12-live-pull-verification-sweep-live-auth-blocker-audit]]"
---

# Exercise expedientes CLI commands with authenticated results, typed empty-state output, and no local-only success masquerading as AEAT evidence

## Scope

- `src/aeat/entrypoints/cli/_app_live_expedientes_cli.py src/aeat/entrypoints/cli/tests`

## Description

- Reconciliation closure for the expedientes CLI command surface. Evidence is
  the offline command-surface guards green at HEAD plus the live authenticated
  typed empty-state result already captured in the live-auth read sweep.

## Outcome

The expedientes CLI is proven to require backend evidence, render typed
empty-state output, and expose only a `pull` acquisition verb (no `pull-all`).

Verification (re-run at HEAD 2026-07-10):

- `uv run --no-sync pytest src/aeat/entrypoints/cli/tests/test_registry_cli.py src/aeat/entrypoints/cli/tests/test_live_read_subgroups.py -q`
  passed (batched run: 18 passed with the filed-rendering, verify, and IVA
  wallet suites); the `pull`-only / no-`pull-all` expedientes guard is included.
- Live positive already on record in the live-auth read sweep exec:
  `app live expedientes pull --modelo 303 --year 2026` returned
  `declaration_count=0` with a persisted encrypted `snapshot_id` and
  `failed_count=0` — a real authenticated typed empty-state result, not a
  local-only success. Raw taxpayer values were redacted; aggregate shape only.

## Notes

- The only authenticated expedientes result available is the empty state, because
  the account carries zero declarations. Typed timeout / portal-drift outcomes
  and broader multi-modelo authenticated coverage remain a matter for the backend
  row S12 and the operator manual sweep S26, both carried forward.
