---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-W12-P26-S252]]'
---

# `secure-storage-production-hardening` `W12.P26.S252` Review

## S252-001 | HIGH | Operator errors rendered raw selector values

`project_review_item` rendered the requested item id in the error message, and `_resolve_internal_kinds` rendered the rejected kind in message/context. Both values can originate from CLI input. The operator errors now use stable localized messages, omit the raw requested item id, and expose only static accepted-kind context for unknown-kind diagnostics.

## S252-002 | PASS | Operator projection stays manifest-scoped

`project_review_queue` resolves the active bucket id through the core profile pointer and delegates source loading to `ReviewQueue.collect`. The row projection does not instantiate repositories or write storage; it maps typed review items into CLI-ready rows.

## S252-003 | PASS | Validation

- `uv run --no-sync ruff check src/aeat/application/review/_operator.py src/aeat/application/review/test_operator.py src/aeat/application/review/test_aggregator.py src/aeat/application/review/test_adapters.py` passed.
- `uv run --no-sync pytest -q src/aeat/application/review/test_operator.py src/aeat/application/review/test_aggregator.py` passed with 8 tests.
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit` passed.

Disposition: close `AFR-150` as `manifest-discovery` with operator diagnostic privacy hardened.
