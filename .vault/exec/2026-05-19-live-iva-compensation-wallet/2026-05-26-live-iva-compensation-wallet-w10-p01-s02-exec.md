---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-05-26'
modified: '2026-05-26'
step_id: 'S02'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
---



# `live-iva-compensation-wallet` `W10.P01.S02`

Completed the bare-exception audit and migrated production exception families
that crossed application, domain, or operator boundaries into the central AEAT
exception hierarchy.

- Modified: `src/aeat/domain/buckets/_errors.py`
- Modified: `src/aeat/application/calculations/_iva_wallet_reconciliation.py`
- Modified: `src/aeat/application/calculations/_iva_compensation_history.py`
- Modified: `src/aeat/application/auth/_operator.py`
- Modified: `src/aeat/application/storage/calc_sheets/_translator.py`
- Modified: `src/aeat/core/errors/registry/_application.py`
- Modified: `src/aeat/core/errors/registry/_domain.py`
- Created: `src/aeat/core/errors/test_exception_base_hygiene.py`
- Modified: `src/aeat/locales/cli.py`
- Modified: `src/aeat/locales/manager.py`
- Modified: `src/aeat/locales/test_parity.py`
- Modified: `src/aeat/locales/test_locale_translation_honesty.py`
- Modified: `src/aeat/locales/en.yml`
- Modified: `src/aeat/locales/es.yml`
- Modified: `src/aeat/locales/ca.yml`
- Modified: `src/aeat/locales/hu.yml`
- Modified: `.vault/plan/2026-05-19-live-iva-compensation-wallet-plan.md`

## Description

The audit removed bare `Exception` and `ValueError` bases from the production
exception families that are part of the AEAT application/domain boundary:
bucket domain errors now derive through `DomainError`, IVA wallet
reconciliation and carry-forward policy input errors derive through
`AeatError`, auth operator errors derive through `AeatError`, and calc-sheets
translation failures derive through `AeatError`.

Each migrated family gained registry coverage so the existing registry
enforcement imports and binds the exception family to a typed code, localized
message key, and CLI suggestion where useful. The remaining direct builtin
exception roots are explicitly classified: the central `AeatError` root,
`SnapshotNotFoundError` as a structural `KeyError` mixin whose concrete
subclasses also inherit `AeatError`, and the private workbook binary-conversion
sentinel caught inside the workbook parity backend.

A static exception-base hygiene test now scans production modules and fails
new classes ending in `Error` or `Exception` when they introduce only Python
builtin exception bases without an explicit allowlist entry. The test avoids
flagging existing AEAT mixins that include a central AEAT base plus a builtin
compatibility base.

The locale maintenance surface was also tightened because this step introduced
new registry and CLI locale keys. Locale catalogue maintenance was run through
`uv run python -m aeat.locales scaffold --sync-locale-parity`, and the CLI now
has a parity-sync mode so dynamic namespace locale drift can be repaired by the
locale CLI instead of hand-editing YAML. The related parity test uses abstract
catalogue files and abstract translation keys only; it does not define
language-specific test surfaces or prose translations.

The official plan-step CLI could not close `W10.P01.S02`; it returned `Step
'W10.P01.S02' does not exist in this plan`. Plain `S02` targets the first
matching row in the repeated L4 plan. The W10 row was therefore closed manually
after the CLI limitation was reproduced.

## Tests

Passed:

- `uv run pytest src/aeat/adapters/persistence/storage/test_errors.py src/aeat/adapters/persistence/storage/bucket/test_bucket_errors.py src/aeat/core/errors/test_exception_base_hygiene.py src/aeat/core/errors/test_registry_enforcement.py src/aeat/entrypoints/cli/test_error_registry_contract.py src/aeat/locales/test_parity.py src/aeat/locales/test_locale_translation_honesty.py -q --disable-warnings`
- `uv run pytest src/aeat/locales/test_parity.py src/aeat/locales/test_locale_translation_honesty.py src/aeat/core/errors/test_exception_base_hygiene.py src/aeat/core/errors/test_registry_enforcement.py src/aeat/entrypoints/cli/test_error_registry_contract.py -q --disable-warnings`
- `uv run ruff check src/aeat/domain/buckets/_errors.py src/aeat/application/calculations/_iva_wallet_reconciliation.py src/aeat/application/calculations/_iva_compensation_history.py src/aeat/application/auth/_operator.py src/aeat/application/storage/calc_sheets/_translator.py src/aeat/core/errors/registry/_application.py src/aeat/core/errors/registry/_domain.py src/aeat/adapters/persistence/storage/errors.py src/aeat/adapters/persistence/storage/bucket/_errors.py src/aeat/locales/cli.py src/aeat/locales/manager.py src/aeat/locales/test_parity.py src/aeat/locales/test_locale_translation_honesty.py`
- `uv run python -m aeat.locales audit`
