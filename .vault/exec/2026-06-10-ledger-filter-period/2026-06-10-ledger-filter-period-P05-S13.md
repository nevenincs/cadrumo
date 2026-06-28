---
tags:
  - '#exec'
  - '#ledger-filter-period'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S13'
related:
  - "[[2026-06-10-ledger-filter-period-plan]]"
---

# Pass a typed core.Period to derive_work_unit_id and WorkUnit in test_modification_refused_when_row_feeds_finalized_modelo

## Scope

- `src/aeat/entrypoints/cli/tests/test_ledger_corpus_journeys.py`

## Description

- Import `Period` from `core` and build `period = Period.from_year_and_code(2025, "1T")`.
- Pass that typed `Period` to both `derive_work_unit_id(..., period=period, ...)` and the `WorkUnit(..., period=period, ...)` constructor, which the typed-core-`Period` refactor (W02.P08) now requires (`ModeloValidationError: expected Period, got str` on the prior `period="1T"`).

## Outcome

Landed in commit `f10720943` (test(ledger-filter-period): pass typed core.Period to work-unit derivation in corpus journey (P05.S13)). Verified green at the then-current HEAD: `test_modification_refused_when_row_feeds_finalized_modelo` passes (1 passed; also green in the earlier three-test reconciliation run).

## Notes

The co-owning ledger-amount-direction campaign left `test_ledger_corpus_journeys.py` uncommitted for ~2 hours (its main C1 absolute-amount/direction-authority work landed separately in `3695a1b93`, but two doc-comment refinements stayed in the working tree). At operator direction this campaign committed the file directly. Because the typed-`Period` fix and the two C1 comment edits were co-mingled in one file and cannot be split without a forbidden `git add -p` / `git stash`, the single commit `f10720943` carries both; the commit message attributes the comment edits to C1. All changes are test/comment-only — no production code changed.
