---
tags:
  - '#exec'
  - '#live-pull-verification-sweep'
date: '2026-07-10'
modified: '2026-07-10'
body_hash: 'sha256:f325101c46963512b4e36fb080b31a7d133f02e6c1281bcfbf310d90cc851efd'
step_id: 'S23'
related:
  - "[[2026-06-12-live-pull-verification-sweep-plan]]"
  - "[[2026-06-12-live-pull-verification-sweep-code-review-audit]]"
---

# Exercise IVA wallet CLI commands after any remote-state wording correction and prove the outputs report pull-only capture status

## Scope

- `src/aeat/entrypoints/cli/_app_live.py src/aeat/entrypoints/cli/tests`

## Description

- Reconciliation closure for the IVA wallet CLI command surface. Evidence is the
  offline IVA wallet CLI suites green at HEAD, which prove the outputs report
  pull-only capture status after the S07 remote-state wording correction
  (`pull-remote-state` retired; wallet acquisition verb is `pull-evidence`).

## Outcome

The IVA wallet CLI reports pull-only capture status; the retired remote-state
verb name is gone from the operator surface.

Verification (re-run at HEAD 2026-07-10):

- `uv run --no-sync pytest src/aeat/entrypoints/cli/tests/test_iva_wallet_correct_cli.py src/aeat/entrypoints/cli/tests/test_iva_wallet_inspector.py -q`
  passed (batched run: 18 passed with the registry/read-subgroup and verify
  suites).
- The operator-facing wording correction is recorded in the code-review audit
  (LPS-002 / LPS-004): the old `pull-remote-state` command now fails with
  `No such command`, and help lists the pull-only `pull-evidence` verb.

## Notes

- No live IVA wallet positive was captured because the authenticated account
  carries zero filed IVA history; the pull-only capture-status wording and CLI
  ergonomics are proven offline. A positive live wallet capture is carried
  forward with the operator manual sweep (S26).
