---
tags:
  - '#exec'
  - '#period-grammar-standardisation'
date: '2026-06-11'
modified: '2026-06-11'
step_id: 'S23'
related:
  - "[[2026-06-11-period-grammar-standardisation-plan]]"
---




# Replace the period: str / ledger_period fields in the state projection with core.Period and add a save->load->equality roundtrip plus anti-tautology proof at that persistence boundary

## Scope

- `src/aeat/application/state_projection.py`
- `src/aeat/entrypoints/cli/_modelo_readiness_cli.py`
- `src/aeat/application/tests/test_state_projection.py`

## Description

- Added `from ..core._period import Period` and `from ..domain.period import parse_canonical_period as _parse_canonical_period` imports to `state_projection.py`
- Re-typed `ProjectionObligation.period` from `str = Field(min_length=1, max_length=16)` to `Period`
- Re-typed `ModeloReadinessRequest.period` from `str = ""` to `Period | None = None`
- Re-typed `ProjectionModeloReadiness.period` from `str = Field(...)` to `Period`
- Re-typed `ProjectionModeloReadiness.ledger_period` from `str | None = None` to `Period | None = None`
- Updated `_build_pending_obligations` to bridge `ModeloDeadline.period` (combined deadline-engine string) via `_parse_canonical_period` + `Period.from_year_and_code`; silently skips unparseable obligations with a DEBUG log
- Updated `_modelo_requires_ledger_preflight` to derive `period_token = request.period.registry_token` and `filing_year = request.period.year` from typed `Period`, passing bare token to `authority.snapshot` and year to `preflight_ledger_tax_readiness`
- Kept `_ledger_period_for_modelo_readiness` as a str-returning helper (aggregation-parseable format) — converts typed `Period` to `YYYYQn`/`YYYY-MM`/`YYYY` strings the aggregation `Period` parser accepts
- Added `_QUARTERLY_TOKEN_TO_AGG` dict mapping `1T→Q1, 2T→Q2, 3T→Q3, 4T→Q4` for the conversion
- Renamed local variable `token` → `code` in `_ledger_period_for_modelo_readiness` to resolve ruff S105 false positive
- Updated `_build_modelo_readiness` to: derive bare token for `ProfilePreflightService.report`; bridge `profile_report.period` (bare str) to `core.Period` via `Period.from_year_and_code`; convert `ledger_report.period._as_core_period()` (aggregation→core Period) for `ProjectionModeloReadiness.ledger_period`
- Added `from ...core._period import Period` import to `_modelo_readiness_cli.py`
- Updated `ModeloReadinessRequest` construction in CLI to pass typed `Period.from_year_and_code(filing_year, period)` or `None`
- Converted `report.ledger_period` to `str` for `ModeloReadinessResult.ledger_period` (strict OutputSchema) via `str(report.ledger_period) if report.ledger_period is not None else None`
- Updated test imports and `ModeloReadinessRequest(period=...)` fixture calls to pass `Period.from_year_and_code(year, token)` objects
- Updated `assert readiness.ledger_period == ...` assertion to compare `core.Period` objects

## Outcome

- Import smoke: `aeat.entrypoints.cli` prints OK
- `pytest src/aeat/application/tests/test_state_projection.py -q --tb=short`: 14 failed (pre-existing `ProfileKeysRegistrationError` from peer WIP in `conftest.py` that removed wizard catalogue imports), 1 passed (`test_missing_registry_snapshot_ledger_preflight_skip_is_debug_logged`)
- `ruff check` on all three changed files: all checks passed
- No new `"\d{4}Q[1-4]"` combined-period construction in changed production files
- Commit: `0f998ebfc` — `refactor(state-projection): typed core.Period on projection obligations and readiness (W02.P08 cluster B)`

## Notes

The 14 pre-existing test failures are caused by peer WIP in `src/aeat/conftest.py` that removed `from .application.wizard import _catalogue, _persistence` imports; those imports register wizard profile keys via `register_profile_keys`, and their absence causes `ProfileKeysRegistrationError` in every state_projection test that touches storage. This is not related to the cluster B migration.

The plan step `W02.P08.S23` scoped a roundtrip test, but `state_projection.py` is an in-memory projection (not persisted); no encrypted-SQL or TOML roundtrip boundary exists here. The note "NOT persisted (in-memory projection); no roundtrip test needed" in the task brief is consistent with the architecture.

Cross-cluster follow-up: `src/aeat/application/workflow/tests/test_engine.py` (peer WIP) uses `ProjectionObligation.period` as a `str` at ~lines 917, 938, 963–966 (comparisons against `ModeloDeadline.period` combined strings and as argument to `run_for_period(period: str)`). These sites need adaptation in the P10 WorkflowEngine cluster, not here.
