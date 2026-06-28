---
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-31'
modified: '2026-05-31'
step_id: S632
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# codebase-solidification W17.P49.S632-S637

Landed 6 closure steps for the W17.P49 audit pass: 3 rationale markers, 1 type narrowing, 1 test refactor, 1 aggregate test.

- Modified: `src/aeat/core/parsing/_dates.py`
- Modified: `src/aeat/entrypoints/cli/_config/_google.py`
- Modified: `src/aeat/application/calculations/_iva_wallet_reconciliation.py`
- Modified: `src/aeat/application/calculations/__init__.py`
- Modified: `src/aeat/adapters/outbound/google/test_calc_sheets_pull_typing.py`
- Created: `src/aeat/test_w17_p49_closure.py`

## Description

S632: Added `BROAD-EXCEPT-RATIONALE-PYDANTIC-PARSE-PROXY` inline comment on all three `raise ValueError(` sites in `_dates.py` (lines 59, 90, 105). Each marker documents that the function is exclusively called from `@field_validator` stacks so the ValueError propagates into the pydantic ValidationError chain — no broad-except escape.

S633: Added `ANY-RETURN-RATIONALE-GOOGLE-OAUTH-STAGING` inline comment on both `installed: dict[str, Any]` fields (`OAuthClientPayload` and `_OAuthClientWrapper`). Documents that the `dict[str, Any]` is the irreducible Google Cloud Console JSON envelope, narrowed to `OAuthClient` by `_coerce_client_json` before any production use.

S634: Confirmed already clean. Both `currency` fields in `_ledger_expenses.py` already use `DEFAULT_CURRENCY` from `aeat.core.external_constants`; no change needed.

S635: Narrowed `prefill_report: Any` to `prefill_report: BindingPrefillReport` in `IvaCompensationReconciliationReport`. Resolved the circular import (`_iva_wallet_reconciliation` → `_binding_prefill` → `_observations_repository` → `_iva_wallet_reconciliation`) by keeping `BindingPrefillReport` under `TYPE_CHECKING` and adding `IvaCompensationReconciliationReport.model_rebuild()` at the end of the package `__init__.py`, after all modules in the cycle are fully loaded. Verified pydantic resolves the annotation to the real class.

S636: Replaced `pytest.skip("no manual casillas found in 130/2T-2024 snapshot")` with `assert manual_casillas, "bundled 130/2T-2024 snapshot must contain at least one MANUAL casilla"`. The bundled snapshot is stable and the skip was a false-negative gate masking test coverage.

S637: Created `test_w17_p49_closure.py` with 10 tests covering all six closure contracts (S632-S636) plus four prior-wave inventory ratchets (`test_utf8_enrollment_inventory`, `test_cast_rationale_inventory`, `test_latin1_encoding_constant_enrollment`, `test_enum_constant_extraction_inventory`). S634 uses AST to exempt `Literal["EUR"]` annotations while catching default-value `"EUR"` literals precisely.

## Tests

`src/aeat/test_w17_p49_closure.py` — 10 tests, all green in 8.97s.

`src/aeat/core/parsing/` + `src/aeat/adapters/outbound/google/test_calc_sheets_pull_typing.py` — 81 passed.

5 pre-existing failures in `test_apoderado.py`, `test_repair_reset_state.py`, and `test_binding_prefill.py::test_modelo_390_prefill_compares_annual_totals_to_persisted_periodic_observations` confirmed pre-existing (no diff against those files); not introduced by this step.

Commit: `a8d643fec`
