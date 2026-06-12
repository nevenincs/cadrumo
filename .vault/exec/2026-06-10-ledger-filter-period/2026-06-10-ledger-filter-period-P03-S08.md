---
tags:
  - '#exec'
  - '#ledger-filter-period'
date: '2026-06-12'
step_id: 'S08'
related:
  - "[[2026-06-10-ledger-filter-period-plan]]"
---

# Migrate test_ledger_list_filter.py from bare YYYY to the canonical year-qualified form

## Scope

- `src/aeat/entrypoints/cli/tests/test_ledger_list_filter.py`

## Description

- Express the annual ledger-list filter as the canonical year-always-separate clauses `period=0A` + `year=YYYY`, replacing any bare-`YYYY` period spelling.
- Add the negative-path coverage that a combined `period=2026Q1` clause refuses with the same AEAT-token guidance as `--period`, naming `--year`.

## Outcome

Landed in commit `c5cdf8fdf` (test(ledger-filter-period): align C6 filter tests to year-always-separate grammar (C6 reconcile)), with filter guidance reuse in `31ca9356a`. Verified at HEAD: the file's filter and refusal tests pass; `git grep -E "2025Q1|2026Q1|period=['\"]?[0-9]{4}['\"]"` returns no stale-notation matches in the file.

## Notes

None.
