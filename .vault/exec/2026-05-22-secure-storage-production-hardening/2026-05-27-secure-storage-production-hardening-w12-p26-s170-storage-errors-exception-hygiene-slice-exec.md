---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'S170'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---



# `secure-storage-production-hardening` `W12.P26.S170` Storage Errors Exception Hygiene Slice

Closed `AFR-068` by verifying the secure-storage exception hierarchy is already rooted in `AeatError` and registry-bound, then repairing the broader exception-base guard regressions surfaced by that verification.

## Changes

- Verified every class in `storage/errors.py` subclasses the AEAT error root and resolves to a registered error code.
- Converted residual application/domain/core bare exception roots to AEAT-rooted exceptions.
- Preserved `ValueError` compatibility for calculation validation errors by using multiple inheritance with `AeatError`.
- Added registry rows for the converted application, core i18n, and bucket-domain exception classes.
- Used existing locale message keys only; no locale file was edited because locale files already have unrelated worktree changes.

## Validation

- `uv run pytest src/aeat/core/errors/test_exception_base_hygiene.py src/aeat/core/errors/test_registry_enforcement.py src/aeat/application/calculations/test_iva_compensation_history.py src/aeat/application/calculations/test_iva_wallet_reconciliation.py src/aeat/application/storage/calc_sheets src/aeat/core/i18n/test_output_language.py src/aeat/core/i18n/test_render_override.py src/aeat/core/i18n/test_translatable_contract.py -q` - 38 passed.
- `uv run pytest src/aeat/core/errors/test_exception_base_hygiene.py::test_production_exception_classes_do_not_introduce_unregistered_builtin_roots -q` - 1 passed.
- Focused `ruff check` over the changed exception and registry files - passed.
- Direct import/registry smoke verified the changed classes subclass `AeatError` and resolve to unique registered codes.
- Focused code review reported no findings.

## Residual Debt

- `uv run pytest src/aeat/core/i18n -q` still fails in `test_placeholder_parity.py` on existing locale placeholder drift. The locale files are already dirty from other work, so this slice records the residual instead of cross-editing them.

## Tracking

Completed internal tasklist for this slice:

- Verify secure-storage exception inheritance and registry enrollment: complete.
- Run the project exception-base guard and identify residual bare roots: complete.
- Convert residual bare roots without losing `ValueError` compatibility: complete.
- Add registry rows without touching dirty locale files: complete.
- Verify tests, lint, plan row closure, and code review: complete.
