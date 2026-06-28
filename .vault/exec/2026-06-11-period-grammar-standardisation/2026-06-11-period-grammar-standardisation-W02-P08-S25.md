---
tags:
  - '#exec'
  - '#period-grammar-standardisation'
date: '2026-06-11'
modified: '2026-06-11'
step_id: 'S25'
related:
  - "[[2026-06-11-period-grammar-standardisation-plan]]"
---




# Replace the period: str fields in the iva prorrata, submission, verification schema, filing schema and modelo export models with core.Period

## Scope

- `src/aeat/domain/iva/_prorrata.py`
- `src/aeat/domain/submission/_models.py`
- `src/aeat/application/verification/_schema.py`
- `src/aeat/domain/filing/_schema.py`
- `src/aeat/application/modelo/_export.py`

## Description

Cluster F scope only (verification/_schema): `VerificationVerdict.period` migrated from
`str` to `aeat.core.Period`. Remaining files from the original S25 scope
(`iva/_prorrata.py`, `submission/_models.py`, `filing/_schema.py`, `modelo/_export.py`)
are out of scope for this execution run and remain as `str` for a follow-up cluster.

- Added `Period` import to `application/verification/_schema.py`; replaced `period: str = Field(...)` with `period: Period`
- Updated module docstring to document the `Period` JSON serialisation shape (`{"filing_year": YYYY, "code": "..."}`)
- Updated `VerificationVerdict` attribute docstring
- Added `Period` import to `application/verification/_verify.py`
- Replaced `_registry_period` + `_filing_period_date` helpers with single `_parse_period(period, ejercicio) -> Period` bridge that calls `parse_canonical_period` + `Period.from_year_and_code`
- Updated `verify_declaracion` to call `_parse_period` once, pass typed `period` to `_load_snapshot` and `period_end_date` directly, and pass `period` (typed `Period`) to `VerificationVerdict`
- Updated `_load_snapshot` signature to accept `period: Period` and use `period.filing_year` / `period.registry_token` for the authority snapshot call
- Removed now-unused `from datetime import date` import
- Updated `TestVerdictJsonRoundTrip.test_verdict_is_json_serialisable` to construct `Period.from_year_and_code(2025, "1T")` and assert round-trip equality plus the reloaded `period` field value

## Outcome

- Import smoke: `aeat.entrypoints.cli` import prints OK
- `pytest src/aeat/application/verification/tests/ -q --tb=short`: 31 passed in 2.22s
- `ruff check` on all three changed files: all checks passed
- No new `"\d{4}Q[1-4]"` literals in production files
- Commit: `17c3f8f23` — `refactor(verification): typed core.Period on VerificationVerdict (W02.P08 cluster F)`

## Notes

`iva/_prorrata.py`, `filing/_schema.py`, `modelo/_export.py` remain as `str` pending
their own cluster runs. `submission/_models.py` (cluster E) is complete — see cluster E
addendum below.

---

## Cluster E addendum — `submission/_models.py` (ModeloPresentado)

### Changes

- Re-typed `ModeloPresentado.period` from `str` to `aeat.core.Period` via a
  `_PeriodField` `Annotated` alias with a `BeforeValidator(_coerce_period)` so
  existing construction sites passing `"2026Q1"` combined strings continue to work.
- Added `_coerce_period` function and `_PeriodField` type alias in `_models.py`.
- Updated `period` attribute docstring to document the `{"filing_year": int, "code": str}`
  JSON serialisation shape across the encrypted-SQL boundary.
- Extended `test_secure_storage_roundtrip.py`:
  - Module-level `_PERIOD = Period.from_year_and_code(2025, "1T")` fixture.
  - Existing roundtrip test now passes a typed `Period` and asserts
    `loaded.period == _PERIOD`, `loaded.period.filing_year == 2025`,
    `loaded.period.registry_token == "1T"`.
  - New `test_submission_corrupted_period_surfaces_at_load`: corrupts the persisted
    `period.code` to `"INVALID_CODE_XYZ"` and asserts `ValidationError` or strict
    inequality on reload (anti-tautology proof for the period field).
- Updated `_complementaria.py`:
  - Added `_period_to_canonical_str(period: Period) -> str` helper that reconstructs a
    canonical period token accepted by `parse_canonical_period` for downstream callers
    that still accept `str` (e.g. `build_draft`).
  - Updated `_SubmittedOriginal` protocol: `period: Period`.
  - `build_complementaria` now does a direct `Period` equality comparison between
    `original_draft.period` and `original_submission.period` (both typed).
  - Reconstructs `_period_str` via the helper for `build_draft(period=...)` and
    `ModeloComplementaria(original_period=...)` arguments.

### Outcome

- `ruff check` on all three changed files: all checks passed.
- `pytest src/aeat/domain/submission/tests/ -q`: 23 passed in 5.73s.
- `test_complementaria.py`: 4 passed / 2 pre-existing failures (peer WIP:
  `ModeloDraft.period` already migrated to `Period` by parallel agent, causing
  `ModeloDraft(period='2024A', ...)` construction sites in those 2 tests to fail
  with `ValidationError`; not caused by this cluster E work).
- Commit: `550a19c10` — `refactor(submission): typed core.Period on ModeloPresentado with roundtrip proof (W02.P08 cluster E)`

---

## Cluster D addendum — `domain/filing/_schema.py` (ModeloDraft)

### Changes

- Re-typed `ModeloDraft.period` from `str` to `aeat.core.Period` (no coercion validator;
  callers must pass a typed `Period` instance).
- Updated `compute_modelo_draft_id` signature: `period: str` → `period: Period`; updated
  hash payload from bare string to `{"filing_year": period.filing_year, "code": period.registry_token}`
  for deterministic, unambiguous content addressing.
- Updated `application/filing/__init__.py` `build_draft(period: str, ...)` (public
  signature unchanged): constructs `Period.from_year_and_code(filing_year, registry_period)`
  internally and passes the typed `Period` to both `ModeloDraft` and
  `compute_modelo_draft_id`.
- Updated `domain/filing/_validator.py`: `self._deadline_checker.check(draft.modelo, draft.period.registry_token)` — extracts bare token string for the `DeadlineChecker.check` protocol.
- Updated `application/filing/_export.py`: `period=str(draft.period)` for `DeclaracionExportResult`; direct `period.filing_year` / `period.registry_token` access for year/code extraction.
- Updated `application/filing/_calculate.py`: `period=str(draft.period)` for `DeclaracionCalculateSummary`.
- Updated `application/filing/_import.py`: `period=str(draft.period)` for `ModeloPresentado` construction (coercion `BeforeValidator` handles the string on that model).
- Updated `domain/submission/_preflight.py`: `is_window_open(draft.modelo, draft.period.registry_token, today)` and `str(draft.period)` in the context dict.
- Updated `application/workflow/_engine.py`: `str(draft.period) != obligation.period` comparison.
- Updated `application/filing/reconciliation/_reconcile.py`: uses `draft.period.registry_token` and `draft.period.filing_year` directly.
- Migrated all `"2026Q1"` / `"2025Q1"` combined-string fixtures in test files to `Period.from_year_and_code(year, token)`:
  - `domain/filing/tests/test_secure_storage_roundtrip.py`
  - `domain/filing/tests/test_roundtrip_anti_tautology.py`
  - `domain/filing/tests/test_amendment_roundtrip.py`
  - `application/filing/tests/test_complementaria_repository.py`
  - `application/filing/tests/test_repository.py`
  - `adapters/persistence/storage/tests/_runtime_migrated_repositories_support.py`
- Fixed `application/filing/tests/test_complementaria.py` `_draft()` helper to convert
  incoming period strings via `parse_canonical_period` + `Period.from_year_and_code`.
- Fixed `application/filing/tests/test_modelo_303_390.py` assertion:
  `assert draft.period == Period.from_year_and_code(*_parse_canonical_period(period))`.
- Fixed `application/filing/reconciliation/tests/test_reconcile.py` `TestRegistryGate`:
  replaced `model_copy(update={"period": "2024A"})` with
  `Period.from_year_and_code(2024, "0A")`.

### Outcome

- `ruff check` on all 26 changed files: all checks passed.
- Full filing suite (domain + application): **272 passed** in 201.69s.
- No new `"\d{4}Q[1-4]"` combined-string literals in production files.
- Commit: `ff68ea22c` — `refactor(filing): typed core.Period on ModeloDraft with roundtrip proof (W02.P08 cluster D)`
