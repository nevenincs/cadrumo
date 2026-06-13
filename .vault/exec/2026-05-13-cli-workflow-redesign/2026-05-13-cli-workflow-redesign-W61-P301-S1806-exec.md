---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'W61.P301.S1806'
related:
  - "[[2026-05-13-cli-workflow-redesign-epic-plan]]"
  - "[[2026-05-13-cli-workflow-redesign-manual-ledger-storage-adr]]"
  - "[[2026-05-13-cli-workflow-redesign-w61-p301-s1801-ledger-storage-ownership-audit]]"
---

# `cli-workflow-redesign` `W61.P301.S1806`

Closed plan rows:

- `W61.P301.S1806`

## Description

Registered and exercised typed bucket-scoped ledger storage errors.

`aeat.domain.transactions` now exposes `LedgerStorageError` and `LedgerNoActiveBucketError`. Blank transaction-catalogue bucket ids raise `LedgerStorageError` with structured context identifying the transaction catalogue repository and object-key operation. Active workflow transaction-catalogue resolution maps the workflow no-active-profile condition into `LedgerNoActiveBucketError` with a recovery suggestion, so non-CLI callers receive a ledger-specific `AeatError` subtype.

The core error registry contains the canonical financial ledger storage codes. Tests now assert the two new classes bind to `FAIL_FINANCIAL_LEDGER_STORAGE` and `REFUSED_FINANCIAL_LEDGER_NO_ACTIVE_BUCKET`.

The global registry was also hardened while closing this step. Stale duplicate registry rows for retired or renamed sanitizer, provider, invoice, LLM, and financial transaction codes were removed; the Google outbound adapter package was made importable so its registered error classes are discoverable; and `AmendmentOverrideCasillaError` was registered under `REFUSED_MODELO_AMENDMENT_OVERRIDE_CASILLA`. The registry gate now has a one-to-one mapping between registered codes and concrete `AeatError` subclasses.

Transaction catalogue repository logging now includes `bucket_id` and `object_key` on load, save, and merge paths, giving storage diagnostics enough context to identify which profile bucket was touched.

## Modified Paths

- `.vault/plan/2026-05-13-cli-workflow-redesign-epic-plan.md`
- `src/aeat/application/workflow/_models.py`
- `src/aeat/application/workflow/test_transaction_catalogue_resolution.py`
- `src/aeat/adapters/outbound/google/__init__.py`
- `src/aeat/core/errors/registry/_adapters.py`
- `src/aeat/core/errors/registry/_domain.py`
- `src/aeat/core/i18n/_render.py`
- `src/aeat/domain/transactions/_errors.py`
- `src/aeat/domain/transactions/_repository.py`
- `src/aeat/domain/transactions/__init__.py`
- `src/aeat/domain/transactions/test_repository.py`
- `src/aeat/entrypoints/cli/_common.py`
- `src/aeat/locales/ca.yml`
- `src/aeat/locales/en.yml`
- `src/aeat/locales/es.yml`
- `src/aeat/locales/hu.yml`

## Tests

- `uv run pytest src/aeat/domain/transactions/test_repository.py -q`
- `uv run pytest src/aeat/domain/transactions/test_repository.py src/aeat/application/workflow/test_transaction_catalogue_resolution.py src/aeat/entrypoints/cli/test_workflow_surface.py src/aeat/application/review/test_adapters.py src/aeat/application/review/test_aggregator.py -q`
- `uv run pytest src/aeat/core/errors/test_registry_enforcement.py src/aeat/core/errors/test_registry.py src/aeat/entrypoints/cli/test_error_registry_contract.py src/aeat/entrypoints/cli/test_error_boundary_integration.py -q`
- `uv run pytest src/aeat/entrypoints/cli/test_profile_output_language.py src/aeat/entrypoints/cli/test_windows_encoding.py -q`

The registry audit reports `orphan_count 0`, `extra_count 0`, and `duplicate_count 0`.
