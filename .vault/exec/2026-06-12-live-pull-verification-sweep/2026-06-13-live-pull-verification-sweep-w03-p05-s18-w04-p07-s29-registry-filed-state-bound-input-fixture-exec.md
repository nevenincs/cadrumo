---
tags:
  - '#exec'
  - '#live-pull-verification-sweep'
date: '2026-06-13'
modified: '2026-06-13'
step_id: 'S18,S29'
related:
  - '[[2026-06-12-live-pull-verification-sweep-plan]]'
  - '[[2026-06-12-live-pull-verification-sweep-code-review-audit]]'
---

# W03.P05.S18 / W04.P07.S29 registry filed-state bound-input fixture

## Scope

Closed the residual registry filed-state red gate surfaced by the row-level
censo calendar review. The failing tests were filed-state verification tests
that constructed a Modelo 130 1T calculation fixture with casilla `05`
supplied as a direct input even though that casilla is now previous-filing
bound.

## Description

- Removed the naked casilla `05` value from `_modelo_130_inputs()` in
  `src/aeat/entrypoints/cli/tests/test_registry_cli.py`.
- The fixture now lets the registry runtime materialise Modelo 130 1T casilla
  `05` through the previous-filing binding path as absent-by-design zero.
- The filed-state verification tests therefore exercise the same source-of-
  truth invariant as production: previous-filing-bound casillas are not allowed
  to enter the calculation as standalone input values.
- This keeps the verification chain aligned with the live filing-state goal:
  local registry recalculation must compare against AEAT-filed observations
  using bound prior-filing evidence, not fixture-smuggled values.

## Verification

- `uv run pytest -m "" src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_verify_filed_state_compares_local_calculation_to_encrypted_observation src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_verify_filed_state_cli_loads_secure_observation_refs src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_verify_filed_state_reports_drift_from_encrypted_observation -q --tb=short`
  - result: 3 passed.
- `uv run pytest -m "" src/aeat/application/overview/tests/test_calendar.py src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py src/aeat/entrypoints/cli/tests/test_registry_cli.py -q --tb=short`
  - result: 120 passed.
- `uv run ruff check src/aeat/entrypoints/cli/tests/test_registry_cli.py`
  - result: passed.

## Live run status

The visible live runner remains at the secure-storage passphrase prompt. This
exec record is local filed-state regression hardening only; it does not claim a
new authenticated AEAT read.
