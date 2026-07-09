---
generated: true
tags:
  - '#index'
  - '#size-budget-refactor'
date: '2026-07-09'
modified: '2026-07-09'
related:
  - '[[2026-07-09-size-budget-refactor-P02-S04]]'
  - '[[2026-07-09-size-budget-refactor-P02-S05]]'
  - '[[2026-07-09-size-budget-refactor-P02-S06]]'
  - '[[2026-07-09-size-budget-refactor-adr]]'
  - '[[2026-07-09-size-budget-refactor-plan]]'
---

# `size-budget-refactor` feature index

Auto-generated index of all documents tagged with `#size-budget-refactor`.

## Documents

### adr

- `2026-07-09-size-budget-refactor-adr` - `size-budget-refactor` adr: `Size-budget offender extraction approach` | (**status:** `accepted`)

### exec

- `2026-07-09-size-budget-refactor-P02-S04` - RAG-ground the calendar module concept, read _calendar.py in full, and identify a cohesive extraction boundary (e.g. per-modelo or per-section calendar builders) that shrinks both the module and build_overview_calendar under their overrides
- `2026-07-09-size-budget-refactor-P02-S05` - Extract the identified cohesive chunk into a new sibling module and re-wire build_overview_calendar to call it, preserving the public API and behavior exactly
- `2026-07-09-size-budget-refactor-P02-S06` - Run the overview test suite, ruff, pytest --collect-only, and test_codebase_size_budgets to confirm the module and callable are under budget with zero behavior drift

### plan

- `2026-07-09-size-budget-refactor-plan` - `size-budget-refactor` plan
