---
tags:
  - '#exec'
  - '#ledger-filter-period'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S06'
related:
  - "[[2026-06-10-ledger-filter-period-plan]]"
---

# Migrate test_ledger_corpus_journeys.py and test_ledger_persona_autonoma_close.py from 2025Q1 to the canonical AEAT token form

## Scope

- `src/aeat/entrypoints/cli/tests/test_ledger_corpus_journeys.py`
- `src/aeat/entrypoints/cli/tests/test_ledger_persona_autonoma_close.py`

## Description

- Replace the combined `2025Q1` period notation with the canonical year-always-separate ledger filter grammar: `--filter period=1T --filter year=2025` (and the matching `--period 1T --year 2025` command form).
- Both files now address the quarter through the shared `Period.contains` boundary, not a private combined-token spelling.

## Outcome

Landed in commit `c1c90df33` (test(ledger-filter-period): migrate stale period notation to canonical AEAT tokens (P03)). Both files were also relocated from `application/aggregation/tests/` to `entrypoints/cli/tests/` by the test-topology refactor. Verified at HEAD: the period-filter call sites use the separate-clause form and pass; `git grep -E '2025Q1|2026Q1'` returns no matches in these files.

## Notes

The plan listed these files under their pre-relocation `application/aggregation/tests/` paths; they now live under `entrypoints/cli/tests/`. `test_ledger_corpus_journeys.py` carried unrelated active peer WIP (the ledger-amount-direction comment edits) at closure time and was not re-touched by this step.
