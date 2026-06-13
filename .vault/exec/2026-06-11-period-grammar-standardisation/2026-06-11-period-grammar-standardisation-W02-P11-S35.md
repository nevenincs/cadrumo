---
tags: ['#exec', '#period-grammar-standardisation']
date: '2026-06-11'
modified: '2026-06-11'
step_id: 'S35'
related:
  - '[[2026-06-11-period-grammar-standardisation-plan]]'
---

# W02.P11.S35 Remove Aggregation Period Wrapper

Scope: remove the residual application aggregation period wrapper and constructor so aggregation exports and tests use `aeat.core.Period` directly.

## Description

- Delete the application-layer `Period` wrapper, `from_year_and_token`, `Quarter`, and `PeriodType` from `_models.py`.
- Re-export `Period` and `PeriodKind` from core at the aggregation package boundary.
- Update modelo binding period resolution to call `Period.from_year_and_code`, validate `has_date_span()`, and translate `PeriodError` into aggregation validation errors.
- Update IVA and Renta aggregation modules to import core period types directly and use `end_date`.
- Update focused aggregation tests and the root tax-fact manipulation test to construct periods with `Period.from_year_and_code` and assert `start_date` / `end_date`.
- Run ruff, focused aggregation tests, CLI import smoke, and review audit.

## Outcome

The aggregation wrapper and wrapper-only constructor are removed from production code. Direct searches found no remaining `from_year_and_token`, wrapper `.start` / `.end`, `Quarter`, or `PeriodType` references in the aggregation period surface. Verification passed with ruff clean, focused tests at `243 passed`, and CLI import smoke printing `OK`.

## Notes

The required RAG query timed out with `HTTP search on port 8766 timed out after 30.0s` and `code=http_search_timeout`; direct `rg` and code inspection provided the grounding. The plan step check saved the S35 checkbox and then crashed during cache invalidation with `LookupError` for `ContextVar _workspace_ctx`; the inspected diff showed only S35 changing from unchecked to checked. The dirty `_retenciones.py` and `test_retenciones.py` files were not edited.
