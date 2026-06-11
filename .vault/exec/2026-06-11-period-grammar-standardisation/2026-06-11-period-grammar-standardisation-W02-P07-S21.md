---
tags:
  - '#exec'
  - '#period-grammar-standardisation'
date: '2026-06-11'
step_id: 'S21'
related:
  - "[[2026-06-11-period-grammar-standardisation-plan]]"
---

# Re-seat application/aggregation Period on core.Period: drop the raw combined-string field, delegate from_year_and_token to core.from_year_and_code, and prove the live ledger-filter parity is preserved

## Scope

- `src/aeat/application/aggregation/_models.py`
- `src/aeat/application/aggregation/_renta_ledger.py`
- `src/aeat/application/aggregation/_renta_income_ledger.py`
- `src/aeat/application/aggregation/_iva_ledger.py`
- `src/aeat/application/modelo/_calculation_actions.py`
- `src/aeat/application/state_projection.py`
- `src/aeat/application/aggregation/tests/test_aggregation.py`
- `src/aeat/application/aggregation/tests/test_renta_ledger_helpers.py`
- `src/aeat/application/tests/test_state_projection.py`

## Description

- Removed `raw: str = Field(...)` stored field from aggregation `Period`; added `extra="forbid"`-safe `raw` pop in the `Mapping` branch of `_parse_raw_period` so persisted records with the field still deserialise.
- Dropped all `raw`-string constructions from `_parse_raw_period` str branch (quarterly, monthly, annual dict payloads no longer set `raw`).
- Removed `_QUARTER_MONTHS` dict and `calendar` import no longer used after date-span delegation.
- Added `_as_core_period()` helper that constructs `core.Period.from_year_and_code(year, registry_token)` on demand, backing `start`, `end`, and `contains`.
- Delegated `start` / `end` computed fields to `_as_core_period().start_date` / `.end_date`.
- Delegated `contains(date)` to `_as_core_period().contains(value)`.
- Rewired `from_year_and_token` to validate span tokens through `core.Period.from_year_and_code` first (refuses non-registry tokens and non-span instalment/extended codes), then wraps as aggregation `Period` without storing a combined string.
- Added `__str__` returning `f"{self.year} {self.registry_token}"` matching `core.Period.__str__` ("2026 1T").
- Updated six call sites that used `period.raw` in error detail strings to use `str(period)` or `registry_token`/`year`.
- Updated `state_projection.py` `ledger_period` assignment from `.raw` to `str(period)`.
- Updated `_calculation_actions.py` error context and suggestion string to use `registry_token` + `year`.
- Updated `test_aggregation.py` to assert `.year` and `.kind` instead of `.raw == "2025Q1"`.
- Updated `test_renta_ledger_helpers.py` to assert `.year == 2025` and `.kind is PeriodKind.ANNUAL` instead of `.raw == "2025"`.
- Updated `test_state_projection.py` `ledger_period` assertion from `"2026Q1"` to `"2026 1T"`.

## Outcome

- Import smoke: `OK`.
- `src/aeat/application/aggregation/tests/`: 432 passed.
- `src/aeat/core/tests/test_period.py` + `src/aeat/entrypoints/cli/tests/test_ledger_period_grammar.py` (marker `integration or not integration`): 107 passed, 3 failed (pre-existing `register_wizard_catalogue` integration-harness failures, excluded per acceptance criteria).
- `ruff check` on all changed files: clean.
- No combined `2026Q1` / `f"{...}Q..."` string constructed or stored by aggregation `Period`.
- Commit: `01bcf3e2a` — `refactor(aggregation): re-seat Period on core.Period, drop combined raw field (W02.P07)`.

## Notes

Peer WIP in `_iva_ledger.py` and `_renta_income_ledger.py` consisted of trailing-comma formatting at lines unrelated to the `.raw` edits. Changes were applied atop that WIP without conflict. The `test_state_projection.py` suite has 14 pre-existing `ProfileKeysRegistrationError` failures (same `register_wizard_catalogue` harness issue); the single test touching my change cannot reach its assertion while the infrastructure failure blocks it. The assertion is correctly updated; the infrastructure failure is pre-existing and not mine.

`state_projection.py` and `_calculation_actions.py` carry a `_ledger_preflight_period_for_work_unit` helper that still constructs combined strings for passing to `Period.model_validate` — these are passing through the existing combined-string *input* path (which continues to parse them), not storing them. Elimination of these helpers is deferred to W02.P08.S23 and later steps per plan.
