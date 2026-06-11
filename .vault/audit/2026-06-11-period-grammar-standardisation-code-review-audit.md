---
tags:
  - '#audit'
  - '#period-grammar-standardisation'
date: '2026-06-11'
related:
  - '[[2026-06-11-period-grammar-standardisation-plan]]'
  - '[[2026-06-11-period-grammar-standardisation-adr]]'
---

# `period-grammar-standardisation` Code Review

<!-- Persistent log of audit findings appended below. -->

## PERIOD-001 | INFO | No findings in IVA authority-source Period slice

Review of commit `62142e93b` found no regressions in the IVA wallet authority-source
period migration. The reviewed slice types authority-source `source_periods` as
`core.Period`, converts prefilled bare registry tokens at the application boundary,
renders reports from `Period.registry_token`, and keeps upstream prefill reports token-based.

Verification reported by the reviewer: focused tests passed with `65 passed`, and a direct
pydantic JSON roundtrip for `IvaCompensationAuthoritySource.source_periods` serialised to
the separated `{"filing_year": ..., "code": ...}` shape and validated back equal.

Residual risk: full-repository and vault checks were not run for this review.

## PERIOD-002 | LOW | Overview fallback still documents a dead combined parser bridge

Review of commit `e6a54068f` found the parser cleanup itself matches the rollout intent:
combined forms refuse, and raw AEAT `nT` only resolves with `ejercicio`.

The remaining issue is in `src/aeat/application/overview/_calendar.py`: `_obligation_period_to_core`
still comments and documents that `parse_canonical_period` handles combined forms, then calls
it without `ejercicio`. After the parser cleanup, that branch no longer handles those forms.
Normal schedule obligations pass `core.Period` and bypass this path, so the risk is stale
fallback documentation rather than a known runtime regression.

This was not fixed in the parser cleanup commit because `src/aeat/application/overview/_calendar.py`
currently contains non-authored WIP in the shared worktree.

Verification reported by the reviewer: `src/aeat/domain/tests/test_period.py` passed with
`41 passed`, and registry schema/query tests passed with `50 passed`.
