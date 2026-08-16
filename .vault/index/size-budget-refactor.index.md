---
generated: true
tags:
  - '#index'
  - '#size-budget-refactor'
date: '2026-08-16'
modified: '2026-08-16'
body_schema: 'body-v1'
body_hash: 'sha256:12cd1b2091c9e31c7d131daf4bb8207d1fbdbea751f75f879f4900ea738ca317'
related:
  - '[[2026-07-09-size-budget-refactor-P01-S01]]'
  - '[[2026-07-09-size-budget-refactor-P01-S02]]'
  - '[[2026-07-09-size-budget-refactor-P01-S03]]'
  - '[[2026-07-09-size-budget-refactor-P02-S04]]'
  - '[[2026-07-09-size-budget-refactor-P02-S05]]'
  - '[[2026-07-09-size-budget-refactor-P02-S06]]'
  - '[[2026-07-09-size-budget-refactor-P03-S07]]'
  - '[[2026-07-09-size-budget-refactor-P03-S08]]'
  - '[[2026-07-09-size-budget-refactor-P03-S09]]'
  - '[[2026-07-09-size-budget-refactor-P04-S10]]'
  - '[[2026-07-09-size-budget-refactor-P04-S11]]'
  - '[[2026-07-09-size-budget-refactor-P04-S12]]'
  - '[[2026-07-09-size-budget-refactor-P04-S13]]'
  - '[[2026-07-09-size-budget-refactor-P05-S14]]'
  - '[[2026-07-09-size-budget-refactor-P05-S15]]'
  - '[[2026-07-09-size-budget-refactor-P05-S16]]'
  - '[[2026-07-09-size-budget-refactor-adr]]'
  - '[[2026-07-09-size-budget-refactor-plan]]'
  - '[[2026-07-10-size-budget-refactor-research]]'
---

# `size-budget-refactor` feature index

Auto-generated index of all documents tagged with `#size-budget-refactor`.

## Documents

### adr

- `2026-07-09-size-budget-refactor-adr` - `size-budget-refactor` adr: `Size-budget offender extraction approach` | (**status:** `accepted`)

### exec

- `2026-07-09-size-budget-refactor-P01-S01` - Record the 6 over-budget module offenders and their owning campaign (secure_objects.py owner-surface, _iva_ledger.py prorrata, _calendar.py owner-surface, _commands.py mcp, _ledger_bindings.py prorrata, _models.py prorrata)
- `2026-07-09-size-budget-refactor-P01-S02` - Record the 6 over-budget callable offenders and their owning campaign (_classify_iva_transaction prorrata, build_overview_calendar owner-surface, taxpayer_profile_from_mapping owner-surface, ledger_add prorrata, build_server mcp, _call_tool mcp)
- `2026-07-09-size-budget-refactor-P01-S03` - Confirm via git log and git diff that each owner-surface target has no uncommitted peer WIP before refactoring
- `2026-07-09-size-budget-refactor-P02-S04` - RAG-ground the calendar module concept, read _calendar.py in full, and identify a cohesive extraction boundary (e.g. per-modelo or per-section calendar builders) that shrinks both the module and build_overview_calendar under their overrides
- `2026-07-09-size-budget-refactor-P02-S05` - Extract the identified cohesive chunk into a new sibling module and re-wire build_overview_calendar to call it, preserving the public API and behavior exactly
- `2026-07-09-size-budget-refactor-P02-S06` - Run the overview test suite, ruff, pytest --collect-only, and test_codebase_size_budgets to confirm the module and callable are under budget with zero behavior drift
- `2026-07-09-size-budget-refactor-P03-S07` - Read taxpayer_profile_from_mapping in full and identify a cohesive extraction boundary (e.g. per-axis mapping helpers) that shrinks it under its override
- `2026-07-09-size-budget-refactor-P03-S08` - Extract the identified cohesive chunk into private helper functions in the same module, preserving the public API and behavior exactly
- `2026-07-09-size-budget-refactor-P03-S09` - Run the deadlines test suite, ruff, pytest --collect-only, and test_codebase_size_budgets to confirm the callable is under budget with zero behavior drift
- `2026-07-09-size-budget-refactor-P04-S10` - Confirm via git log that secure_objects.py has no uncommitted or actively landing peer WIP from the secure-persistence campaign before starting
- `2026-07-09-size-budget-refactor-P04-S11` - Read secure_objects.py in full and identify a cohesive extraction boundary that shrinks it under its override, preserving the public API and behavior exactly
- `2026-07-09-size-budget-refactor-P04-S12` - Extract the identified cohesive chunk into a sibling module and re-wire callers, preserving the public API and behavior exactly
- `2026-07-09-size-budget-refactor-P04-S13` - Run the storage roundtrip test suite, ruff, pytest --collect-only, and test_codebase_size_budgets to confirm the module is under budget with zero behavior drift
- `2026-07-09-size-budget-refactor-P05-S14` - Record _iva_ledger.py, _classify_iva_transaction, _ledger_bindings.py, _models.py, and ledger_add as deferred to the prorrata campaign (peer-hot files under active churn) with no code changes made
- `2026-07-09-size-budget-refactor-P05-S15` - Record _commands.py, build_server, and _call_tool as deferred to the mcp campaign (peer-hot files under active churn) with no code changes made
- `2026-07-09-size-budget-refactor-P05-S16` - Confirm test_codebase_size_budgets fails only on the 6 deferred peer-owned offenders after the owner-surface Phases land, and record this green-except-peer state

### plan

- `2026-07-09-size-budget-refactor-plan` - `size-budget-refactor` plan

### research

- `2026-07-10-size-budget-refactor-research` - size-budget-refactor research: warning closeout research grounding
