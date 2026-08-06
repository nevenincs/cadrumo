---
tags:
  - '#exec'
  - '#live-pull-verification-sweep'
date: '2026-07-10'
modified: '2026-07-10'
body_hash: 'sha256:cfe32be51d2192adc801f1f4887654726f47b0de5411d27687fcf6bbc09c3e7f'
step_id: 'S15'
related:
  - "[[2026-06-12-live-pull-verification-sweep-plan]]"
  - "[[2026-06-12-live-pull-verification-sweep-code-review-audit]]"
---

# Prove IVA wallet and IVA remote acquisition are pull-only captures over filed history and wallet evidence, with no remote-state return or push semantics

## Scope

- `src/aeat/application/live/_iva_remote_state.py src/aeat/application/live/_iva_remote_state_outcomes.py src/aeat/entrypoints/cli/_app_live.py`

## Description

- Reconciliation closure for the IVA wallet / IVA remote acquisition backend
  facade. Evidence is the offline real-behavior acquisition suite green at HEAD,
  proving the facade is a pull-only capture over filed history and wallet
  evidence with typed outcomes and no remote-state return or push semantics.

## Outcome

The IVA remote-state acquisition backend is proven pull-only by real-behavior
tests green at HEAD.

Verification (re-run at HEAD 2026-07-10):

- `uv run --no-sync pytest src/aeat/application/live/tests/test_iva_remote_state_acquisition.py -q`
  passed (batched run: 34 passed with the borrador and CLI-verb suites).
- The acquisition path returns typed capture outcomes with no push, submit, or
  bidirectional remote-state write verb, consistent with the S07 operator
  vocabulary correction that renamed the wallet verb to `pull-evidence`
  (code-review audit LPS-002 / LPS-004).

## Notes

- No live IVA wallet or filed-IVA positive was captured because the
  authenticated account carries zero filed declarations; the pull-only contract
  and typed outcomes are proven offline against real behavior. A positive live
  wallet capture depends on an account with filed IVA history and is carried
  forward with the operator manual sweep (S26).
