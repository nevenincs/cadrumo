---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-W12-P26-S252]]'
---

# `secure-storage-production-hardening` `W12.P26.S252` Review

## S252-001 | HIGH | Operator errors rendered raw selector values

`project_review_item` rendered the requested item id in the error message, `_resolve_internal_kinds` rendered the rejected kind in message/context, and `ReviewKindReservedError` rendered the reserved token directly. These values can originate from CLI input. The operator errors now use stable localized messages, omit raw requested item ids and kind tokens, and expose only static accepted-kind or reserved-reason context.

## S252-002 | HIGH | Review CLI bypassed central translated error rendering

The review CLI caught `ReviewError` and raised `BadParameter(str(exc))`, bypassing `resolve_error_message`. Errors that carried `translated_message` keys could therefore surface fallback internal strings rather than localized operator text. The review CLI now renders domain errors through the central error resolver before crossing the Typer boundary.

## S252-003 | PASS | Operator projection stays manifest-scoped

`project_review_queue` resolves the active bucket id through the core profile pointer and delegates source loading to `ReviewQueue.collect`. The row projection does not instantiate repositories or write storage; it maps typed review items into CLI-ready rows.

## S252-004 | PASS | Validation

- `uv run --no-sync ruff check src/aeat/application/review/_operator.py src/aeat/application/review/_errors.py src/aeat/application/review/test_operator.py src/aeat/entrypoints/cli/_review.py src/aeat/entrypoints/cli/test_review_operator_errors.py` passed.
- `uv run --no-sync pytest -q src/aeat/application/review/test_operator.py src/aeat/entrypoints/cli/test_review_operator_errors.py src/aeat/entrypoints/cli/test_error_registry_contract.py` passed with 12 tests.
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit` passed.

Disposition: keep `AFR-150` closed as `manifest-discovery` with operator diagnostic privacy and CLI translated rendering hardened.
