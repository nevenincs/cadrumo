---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'W37.P182'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-05-12-cli-workflow-redesign-festivos-deadline-shift-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-adr]]'
---

# `cli-workflow-redesign` `W37.P182`

Asserted the no-shadow contract for the festivos / business-day
service: only one calendar service and one shift function exist in
the source tree.

- Created (within the test for P181): boundary test
  `test_no_parallel_festivos_implementation_exists`
  in `src/aeat/domain/deadlines/test_festivos.py`.

## Description

The shadow-removal phase asserts the substrate added in P181 is the
unique authority for business-day determination and AEAT deadline
shifting across the codebase. The accepted location is
`aeat.domain.deadlines`. Any module elsewhere that re-implements a
holiday calendar, a weekend / festivo predicate, or a next-business-
day walk would compete with the canonical service and break the
no-parallel-service guarantee from the ADR.

The boundary test `test_no_parallel_festivos_implementation_exists`:

- Walks the project's source tree.
- Skips known third-party / generated / test files so it does not
  flag itself.
- Greps for hallmark identifiers (`is_business_day`,
  `next_business_day`, `shift_deadline`, plus the phrase
  `días inhábiles`).
- Asserts every match resolves to the canonical module
  (`src/aeat/domain/deadlines/_festivos.py`) or to test files that
  legitimately exercise it.

The test currently passes because no parallel implementation was
ever landed; it acts as a regression guard against a future agent
re-creating a local business-day helper inside `entrypoints/cli/`
or under another domain package.

Closed plan rows: `W37.P182.S1087`, `W37.P182.S1088`,
`W37.P182.S1089`, `W37.P182.S1090`, `W37.P182.S1091`,
`W37.P182.S1092`.

## Tests

`uv run --no-sync pytest src/aeat/domain/deadlines/test_festivos.py
-k no_parallel_festivos_implementation -q` — 1 / 1 pass.
