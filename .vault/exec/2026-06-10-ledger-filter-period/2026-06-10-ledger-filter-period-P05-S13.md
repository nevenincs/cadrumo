---
tags:
  - '#exec'
  - '#ledger-filter-period'
date: '2026-06-12'
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

Fix applied in the working tree (concurrently by the typed-`Period` / co-editing agents) and VERIFIED PASSING: `test_modification_refused_when_row_feeds_finalized_modelo` passes in the three-test reconciliation run (3 passed).

NOT yet committed by this campaign. The file simultaneously carries unrelated uncommitted WIP from the ledger-amount-direction campaign (doc-comment refinements at the `test_operator_can_filter_income_vs_expense` and `test_transfer_row_reclassified...` sites). Committing the file here would co-opt that peer campaign's edits into a ledger-filter-period commit, which the `aeat-git-worktree-safety` explicit-pathspec discipline forbids. The commit is therefore deferred to the agent that owns the file's WIP.

## Notes

Step left UNCHECKED per `plan-closure-requires-exec-records` (intentional deferral, blocker named): the fix is applied and green, but the owning commit belongs to the concurrent campaign co-editing `test_ledger_corpus_journeys.py`. Once that campaign lands its commit (carrying both the typed-`Period` fix and its own comment edits), this step can be checked. The verification evidence above stands independent of which commit ultimately carries the line.
