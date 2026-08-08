---
tags:
  - '#exec'
  - '#history-onboarding'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:a0856ea1c7d8aa072fc5a091bc70a99668ad75d404df8c3bc479aaf4c391e592'
step_id: 'S08'
related:
  - "[[2026-08-07-history-onboarding-plan]]"
---




# add the pull_filed_history orchestration service walking the FiledHistoryDiscoveryReport union grid, calling capture_filed_data_bulk over it, then capture_iva_compensation_wallet and reconcile_iva_compensation_wallet, then the existing notificaciones pull, verified by an integration test against synthetic fixtures for every stage asserting the composed FiledHistoryOnboardingResult reflects every stage's outcome

## Scope

- `src/cadrumo/application/live/_filed_data_capture.py`

## Description

- Add `FiledHistoryOnboardingRun` and `FiledHistoryPairOutcome`.
- Add `pull_filed_history`, sequencing discovery, bulk capture, IVA wallet and notificaciones.

## Outcome

Composes existing primitives and adds no capture mechanism. In particular it does
NOT wrap the register walk in its own error handling: the bulk sweep already
absorbs any walk failure — including the truncated-page refusal — into a typed
failure row and continues, so wrapping it again would duplicate that authority and
could swallow the very failure row the taxonomy exists to produce.

Each LATER stage is guarded separately, because the stages are independent: a
notificaciones timeout says nothing about whether the filed capture succeeded, and
losing a long authenticated sweep to an unrelated failure would waste it. A
partial run reports which stage failed rather than collapsing into one error.

The run exposes `refused_pairs` and `genuinely_empty_pairs` as separate
projections so no consumer has to infer a refusal from a zero row count.

## Verification

uv run --no-sync pytest src/cadrumo/application/live/tests/ src/cadrumo/application/overview/tests/ \
      src/cadrumo/entrypoints/cli/tests/test_app_live_filed_discover.py \
      src/cadrumo/entrypoints/cli/tests/test_filed_history_onboarding_result.py \
      src/cadrumo/entrypoints/cli/tests/test_json_schema_conformance.py \
      src/cadrumo/entrypoints/cli/tests/test_documented_command_conformance.py \
      src/cadrumo/agent/tests/test_rule_surface_conformance.py -q -n0 -m "unit or integration"
    1147 passed, 2 deselected in 155.20s (0:02:35)

## Notes

No live AEAT session is opened by any test here; the run model and its
projections are pure functions over an already-composed run. The live sequencing
itself needs an authenticated session and no live probe is authorised, so that arm
is exercised only through the composed primitives' own gates rather than being
simulated — a fabricated AEAT form would read as coverage while proving nothing.
