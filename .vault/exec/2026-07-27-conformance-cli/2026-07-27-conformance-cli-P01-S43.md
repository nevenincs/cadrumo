---
tags:
  - '#exec'
  - '#conformance-cli'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S43'
related:
  - "[[2026-07-27-conformance-cli-plan]]"
---

# add a fixed lower bound to the signoff horizon so a review dated before the revision existed refuses, mirroring the ceiling that already catches the far-future sentinel

## Scope

- `src/cadrumo/domain/calculations/registry/_schema.py`

## Description

- Read `_schema.py` in full to locate `_reviewed_at_is_within_the_signoff_horizon` and `REVISION_REVIEW_DATE_CEILING`.
- Verified no peer WIP on `_schema.py` or `test_governance_stamp.py` via `git diff -- <file>`.
- Extended `_reviewed_at_is_within_the_signoff_horizon` to also refuse a `reviewed_at` date strictly before `REVISION_REVIEW_DATE_FLOOR`, raising `RegistryValidationError` with message matching `"signoff floor"`.
- Added `REVISION_REVIEW_DATE_FLOOR = date(2000, 1, 1)` constant below `REVISION_REVIEW_DATE_CEILING` with docstring explaining it is a fixed absurdity floor (not clock-consulting, not a freshness gate), sized to reject the full Unix-epoch / template-sentinel class.
- Added `REVISION_REVIEW_DATE_FLOOR` to the `__all__` export of `_schema.py`.
- Added `REVISION_REVIEW_DATE_FLOOR` to the import in `test_governance_stamp.py`.
- Added `test_reviewed_at_before_the_signoff_floor_is_refused`: loads a revision with `reviewed_at = 1970-01-01`, asserts `RegistryLoadError` matching `"signoff floor"`.
- Added `test_a_date_at_the_signoff_floor_still_loads`: loads a revision with `reviewed_at = 2000-01-01`, asserts the loaded value equals `REVISION_REVIEW_DATE_FLOOR` (differential boundary proof).
- Updated `test_bundled_revisions_carry_a_coherent_stamp` to assert `revision.reviewed_at >= REVISION_REVIEW_DATE_FLOOR` alongside the existing ceiling check, covering the full bundled tree (90 revisions).
- Ran `uv run --no-sync pytest src/cadrumo/domain/calculations/registry/tests/test_governance_stamp.py -n0 -q` — 33/33 passed.
- Ran `uv run --no-sync ruff check src/cadrumo/domain/calculations/registry/_schema.py src/cadrumo/domain/calculations/registry/tests/test_governance_stamp.py` — clean.
- Committed with explicit pathspec as `b55f2def84`.

## Outcome

33 tests passed, 0 failed. Ruff clean. The bundled registry tree (73 modelos, 90 revisions) continues to load without error. Sentinel dates before the year 2000 (1970-01-01, 1900-01-01, 0001-01-01) now refuse at `RegistryLoadError` with a message naming the floor. The date-at-floor boundary differential confirms the refusal is a strict `< FLOOR` check, not a blanket rejection of older dates.

## Notes

Discovery gate waived by operator — the vaultspec-rag index was broken and the service stopped. Grounded with `rg` plus whole-file reads in lieu of semantic search.

The validator body references `REVISION_REVIEW_DATE_FLOOR` before its definition site in the file; this is safe because field validators run at instance creation time, not at class definition time.
