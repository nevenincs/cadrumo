---
tags:
  - '#exec'
  - '#profile-requirement-grounding'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:ae8ef73f5d64e8f1cf0907e6e912b09d2ba0cd2597c977d5532197aa31705c36'
step_id: 'S12'
related:
  - "[[2026-08-08-profile-requirement-grounding-plan]]"
---

# `profile-requirement-grounding` P05.S12

Make the unevaluated per-modelo case distinguishable from a passing one on `ProfilePreflightReport`, so a modelo matching no schema-required field reports not-assessed rather than ready.

## Scope

- `src/cadrumo/application/user_profile/_commands.py`
- `src/cadrumo/application/user_profile/_preflight.py`
- `src/cadrumo/application/user_profile/tests/test_preflight_reports_unassessed_axis.py`

## What landed

Commit `ace2a2e2fe` (3 files, +156). Added `ProfilePreflightReport.per_operation_requirements_assessed`, populated in `ProfilePreflightService.report()` from whether the per-modelo walk selected any schema-required field.

Three decisions worth recording, because each had a plausible alternative:

**The counter tracks SELECTION, not failure.** A modelo whose selected fields are all present is genuinely assessed and ready; counting only missing fields would have made a passing modelo indistinguishable from an unassessed one, which is the exact conflation this Step exists to remove.

**The field carries no default.** There is exactly one producer (`_preflight.py:113`, verified by grep before choosing), so requiring it costs nothing and a default would silently assert an assessment that never ran.

**`ready` is deliberately unchanged.** Deriving `ready` from assessment was the obvious reading of the amendment's ruling 1, and it is wrong: `_profile_readiness_gate.py:530-541` raises on `not report.ready`, and the axis is empty for *every* modelo, so that derivation would refuse all filing work application-wide. The signal is additive; rendering it as an operator notice is P05.S13.

The `report()` docstring described the per-modelo walk as though it selected fields. It now states that no shipped field declares such a selector and that a false flag must not be rendered as a clean bill of health.

## Verification

`pytest src/cadrumo/application/user_profile/tests/` — **440 passed**. Ruff check, ruff format --check, and ty all clean on the three files.

The test design is the load-bearing part. No shipped schema field declares a `modelo_` selector, so the production population for this flag is empty in one direction — a suite asserting only the shipped case would pass against a flag hardcoded `False` and prove nothing. The positive controls therefore build a **real** `ProfileSchemaDefinition` whose required field declares `modelo_303` and drive it through the real service. One negative case pins the near-miss that made the shipped schema read as populated in the first place: `withholding.modelo_111_no_retenciones_periods` contains the substring but is a field path, so a containment test rather than a prefix test would wrongly count it.

Two-directional mutation proof, run from outside the repo:

| mutation | red |
|---|---|
| `per_operation_requirements_assessed` hardcoded `False` | 2 / 5 — both positive controls |
| hardcoded `True` | 3 / 5 — all three negative cases |

Every test bites in exactly one direction and all five are covered by one mutation or the other, so none is vacuous.

## Not done here

The signal is computed and carried but not yet surfaced to an operator — `config profile preflight` and `app modelo readiness` still render the same output. Until P05.S13 lands, the unassessed grant is visible in the model and **not** on any operator surface, so this Step does not by itself close the honesty gap the amendment describes.

## Unrelated failure observed, not actioned

`application/modelo/tests/test_modelo_202_modality_lifecycle.py::test_m202_wrong_state_still_refuses_file_before_required_binding_gate` fails at this HEAD with `NoRevisionForPeriodError: modelo 200: no revision for year=2024 period='0A'`. Attributed to peer commit `515f4c502b`, which moved the M200 `2024-y-siguientes` `valid_from` from 2024-01-01 to 2025-01-01, one commit after `5349920031` restored it to 2024-01-01. Outside this Step's surface and belonging to the M200 registry campaign; reported to the coordinator rather than fixed here.
