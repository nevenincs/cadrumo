---
tags:
  - "#exec"
  - "#unified-review-queue"
date: 2026-04-18
modified: '2026-04-18'
related:
  - "[[2026-04-18-unified-review-queue-plan]]"
  - "[[2026-04-18-unified-review-queue-adr]]"
  - "[[2026-04-18-unified-review-queue-phase1-summary-exec]]"
  - "[[2026-04-18-unclassified-state-adr]]"
---

# unified-review-queue phase-2 summary

Rolling-audit pass on PR #258. Phase 1 shipped the aggregator; phase 2 integrated upstream changes that landed on `main` while the PR was open and discovered + closed several test-coverage and stale-doc gaps.

## scope of this phase

Three iteration loops:

1. **Gemini-PR action loop** — declined the `is`/`is not` → `==`/`!=` suggestion (project convention), removed dead `_STDERR`, simplified aggregator with unpacked-spread.
2. **Sibling-PR drift loop (#251 corpus rename)** — merged main, resolved `kent-capabilities.md` + `aeat-project-mandates.md` conflicts, confirmed no broken references.
3. **Sibling-PR drift loop (#252 / #237 BusinessClassification split)** — large impact: legacy `UNCLASSIFIED` enum value deleted, four new states added, `is_classified()` helper added, AND a competing `aeat review history` command added in the same `cli/review/` namespace.

## phase-2 findings (rolling audit)

### Gemini-PR pass
- `[ADJUST]` Dead `_STDERR = Console(stderr=True)` in `cli/review/queue.py` → removed.
- `[ADJUST]` `cast(list[ReviewItem], list(func()))` chain in `_aggregator.py` → replaced with unpacked-spread literal.
- `[ADJUST]` `_all_kinds()` helper in `_aggregator.py` was dead → removed.
- `[OK]` Gemini's `is`/`is not` → `==`/`!=` suggestion declined (declined: project uses `is` uniformly across `cli/financial/txs.py:43`, `financial/transactions/_models.py:155`, etc.). Reply posted; Gemini accepted.

### #251 (corpus rename) drift
- `[BLOCK]` Conflict in `docs/coverage/kent-capabilities.md` → kept #232 row; resolved.
- `[BLOCK]` Conflict in `.vaultspec/rules/rules/aeat-project-mandates.md` → adopted main's improved trilingual wording.
- `[OK]` `normatives.reviewed_by` intentionally untouched per #251 research scope.

### #252 / #237 (BusinessClassification split) drift — HIGH-impact
- `[BLOCK]` `_adapters.py:79` referenced deleted `BusinessClassification.UNCLASSIFIED` → migrated to `is_classified()` + first-match-wins severity per the four new states.
- `[BLOCK]` `cli/review/__init__.py` add/add conflict with the new `aeat review history` command → combined both commands under one Typer sub-app.
- `[BLOCK]` Auto-merge produced duplicate `app.add_typer(review_module.app, ...)` in `cli/__init__.py` → removed the second registration.
- `[ADJUST]` Test fixtures used `BusinessClassification.UNCLASSIFIED` → migrated to `NOT_YET_PROCESSED` baseline.
- `[ADJUST]` No tests covered the new richer state model → added parametric `test_transactions_pending_severity_mapping` (3 states) + `test_transactions_pending_skips_skipped_by_rule`.
- `[ADJUST]` ADR D2 / D5 / D7 still described the pre-#237 enum → rewrote transactions section + severity table.
- `[ADJUST]` Plan + research used pre-#237 predicate → updated to `not is_classified(state) AND state is not SKIPPED_BY_RULE`.
- `[ADJUST]` `_models.py:50` docstring still said `(UNCLASSIFIED)` → updated to name the three new pending states.

### Coverage-gap loop
- `[ADJUST]` `_adapters.py:204` (non-PENDING divergence skip) was uncovered → added `test_divergences_pending_skips_non_pending_records`.
- `[ADJUST]` `_classify_finding` INFO branch uncovered → extended findings test to include INFO severity.
- `[ADJUST]` `drafts_pending` placeholder for `status=DRAFT` was uncovered (only VALIDATED tested) → added `test_drafts_pending_emits_placeholder_for_draft_status`.

### Stale-doc loop
- `[ADJUST]` `docs/coverage/pipeline.md` had three stale cells citing #232 as ⏳ scheduled / ❌ not scoped → all three flipped to ✅.
- `[ADJUST]` `docs/coverage/kent-capabilities.md` row 26 already updated in phase 1 (CLI-supported + Tested → ✅).

## final verification

- `uv run pytest src/aeat/review src/aeat/entrypoints/cli/review` — **57 tests pass** (49 from phase 1 + 4 new transaction-state tests + 2 new history tests adopted from #252's `test_review.py` + 2 new placeholder/finding-INFO tests).
- `uv run pytest -m unit` — **1859 passed** (no regressions; project gained 73 unit tests across all merged PRs since phase 1).
- `uv run ruff check` — clean.
- `uv run ruff format --check` — clean.
- `uv run ty check src tests` — clean (project-wide).
- `uv run aeat review --help` — both `queue` and `history` commands surface under one sub-app.
- CI: Ubuntu + Windows / Python 3.13 — both `SUCCESS` post-merge.
- PR `mergeable: MERGEABLE`, `mergeStateStatus: CLEAN`.

## audit-pool convergence

The remaining uncovered lines on `src/aeat/review` (now 90.x% coverage; was 92% pre-merge — diluted by the new state-mapping branches added in this phase) are all defensive exception paths (OSError on file load, ValidationError edge cases) or the four time-formatting branches in `_relative_since`. Adding tests for each defensive branch would be busywork without product value.

The audit pool for this PR is exhausted. Each rolling pass surfaced fewer findings; this phase's findings were nearly all upstream-drift integrations rather than original code defects. Further audits should now target other PRs / other subpackages.

## phase-2 commit history

- `52291bb` refactor(review): drop dead code (Gemini pass)
- `baecf31` Merge with origin/main (#251 corpus rename conflicts)
- `fa655d2` test(review): cover non-PENDING + INFO + DRAFT paths
- `8cbaa1e` docs(coverage): pipeline matrix reflects shipped queue
- `7a34038` Merge with origin/main + post-#237 BusinessClassification migration
- (this commit) docs(exec): phase-2 summary
