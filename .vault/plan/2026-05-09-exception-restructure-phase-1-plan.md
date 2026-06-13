---
tags:
  - "#plan"
  - "#exception-restructure"
date: 2026-05-09
modified: '2026-05-09'
related:
  - "[[2026-05-09-exception-restructure-research]]"
  - "[[2026-05-09-exception-restructure-adr]]"
---
# Exception Restructure Plan (Revised)

## Overview
Recent feedback refocused this plan. Instead of moving all exception definitions strictly into `src/aeat/core/errors/`, it is acceptable to maintain exceptions within their domain or boundary modules, provided they strictly inherit from the core `AeatError`. The true blocker is the presence of "naked" standard library exceptions (e.g., `ValueError`, `RuntimeError`, `KeyError`) raised as domain errors.

## Execution Checklist

### Phase 1: Audit and Enforce Core Inheritance
For the ~55 files containing custom exceptions (as inventoried in the research document), we will audit each definition and ensure it inherits directly or transitively from `AeatError`.
- [x] Audit `GoogleAuthUnavailableError` in `src/aeat/adapters/outbound/google/__init__.py` (currently inherits from `RuntimeError`).
- [x] Audit `UserProfileSchemaLoadError` in `src/aeat/domain/user_profile/_errors.py` (currently inherits from `ValueError`).
- [x] Audit `PathContainmentError` in `src/aeat/adapters/persistence/storage/errors.py` (currently inherits from `ValueError`).
- [x] Ensure all remaining exceptions correctly subclass `AeatError`.

### Phase 2: Refactor Naked Exceptions
We will progressively audit the codebase (where `grep` identified 500+ instances of naked exceptions such as `ValueError`, `RuntimeError`, `KeyError`, `TypeError`) and replace them with appropriate domain-specific, `AeatError`-derived subclasses.

*Batch 1: Core and CLI Entrypoints*
- [x] Audit and refactor naked exceptions in `src/aeat/entrypoints/cli/_common.py`.
- [x] Audit and refactor naked exceptions in `src/aeat/entrypoints/cli/financial/txs.py`.
- [x] Audit and refactor naked exceptions in `src/aeat/entrypoints/cli/browser/test_health.py`.
- [x] Define and enrich localized `AeatError` subclasses to carry the former `ValueError` messages.

*Batch 2: Domain Layer (Transactions & VAT)*
- [x] Audit and refactor naked exceptions in `src/aeat/domain/transactions/_llm.py`.
- [x] Audit and refactor naked exceptions in `src/aeat/domain/transactions/_raw_transaction.py`.
- [x] Audit and refactor naked exceptions in `src/aeat/domain/transactions/_model_tier.py`.
- [x] Audit and refactor naked exceptions in `src/aeat/domain/transactions/_models.py`.
- [x] Audit and refactor naked exceptions in `src/aeat/domain/vat/_rates.py`, `_schema.py`, `_recargo_equivalencia.py`, `_classification.py`, `_oss.py`.
- [x] Define `TransactionValidationError` and `VatValidationError`.

*Batch 3: Additional Domains (Normatives, Renta, User Profile)*
- [x] Audit and refactor naked exceptions in `src/aeat/domain/normatives/_schema.py`.
- [x] Audit and refactor naked exceptions in `src/aeat/domain/renta/_ledger_expenses.py`.
- [x] Audit and refactor naked exceptions in `src/aeat/domain/user_profile/_values.py` and `_schema.py`.
- [x] Define `NormativeValidationError`, `RentaValidationError`, `UserProfileValidationError`.

*Batch 4: Auth Adapters (`src/aeat/adapters/outbound/aeat/auth/`)*
- [x] Centralise shared errors in `auth/_errors.py`
- [x] Refactor `certificate.py` to use `AuthError` base
- [x] Refactor `_clave_movil.py` to use `AuthConfigurationError`
- [x] Refactor `select_provider` in `auth/__init__.py` to use `AuthConfigurationError`
- [x] Ensure `Authenticator` uses shared login/session errors

*Batch 5: Export & Formats (`src/aeat/adapters/outbound/aeat/export/`)*
- [x] Define `ExportError` and `ExportFormatError` in `export/_errors.py`
- [x] Refactor `_serialise.py` to use `ExportFormatError`
- [x] Refactor `_record_spec.py` to use `ExportFormatError`
- [x] Refactor application layer `_export.py` to use domain errors

*Batch 6: Inbound Adapters (PDF, NIF)*
- [x] Audit `src/aeat/adapters/inbound/pdf/` for naked exceptions
- [x] Audit `src/aeat/adapters/inbound/nif/` for naked exceptions

*Batch 7: Domain Models (Filing, Models, etc.)*
- [x] Audit `src/aeat/domain/filing/` for naked exceptions
- [x] Audit `src/aeat/domain/models/` for naked exceptions

### Phase 3: Testing and Validation
- [x] Verify NO tautological calculation tests have been written regarding error shapes.
- [x] Write integration boundary test ensuring `AeatError` is properly caught, using a realistic setup instead of self-reaffirming conditions.
  - Implemented in `src/aeat/entrypoints/cli/test_error_boundary_integration.py`.
  - Two parametrized probes: flag-collision (`--quiet --verbose`) and invalid env (`AEAT_LOG_LEVEL=NOT_A_VALID_LEVEL`).
  - Expected exit codes read from live `get_error_exit_code()` — not hardcoded literals.
  - No mocks, patches, stubs, or fakes.
