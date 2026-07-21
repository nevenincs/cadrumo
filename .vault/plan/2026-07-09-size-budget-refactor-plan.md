---
tags:
  - '#plan'
  - '#size-budget-refactor'
date: '2026-07-09'
modified: '2026-07-17'
tier: L2
related:
  - '[[2026-07-09-size-budget-refactor-adr]]'
  - '[[2026-07-10-size-budget-refactor-research]]'
---

# `size-budget-refactor` plan

## Description

`test_codebase_size_budgets.py` (both the module-line and the callable-line
gate) is red on 12 offenders: 6 modules and 6 callables that have grown past
their per-file/per-callable override ceilings. The operator opened this as
its own campaign, separate from the perf/registry campaign that discovered
it, because half the offenders sit inside files under active churn by other
concurrent campaigns (prorrata, mcp) and refactoring them now would be a
collision hazard, not a fix.

The offenders split cleanly into two groups by last-touch ownership:

- **Owner-surface stable** (no recent or in-flight peer commits): `_calendar.py`
  (module 1677 > 1667, `build_overview_calendar` 202 > 192),
  `_profiles.py:taxpayer_profile_from_mapping` (196 > 180), and
  `secure_objects.py` (1312 > 1295, conditional on the secure-persistence
  campaign being quiet on it at execution time). These are refactored by this
  plan.
- **Deferred peer-churning**: `_iva_ledger.py` / `_classify_iva_transaction`,
  `_ledger_bindings.py`, `_models.py` (transactions), and
  `_ledger.py:ledger_add` belong to the prorrata campaign; `_commands.py`
  (wizard) and `_server.py:build_server` / `_call_tool` belong to the mcp
  campaign. This plan records them and leaves them untouched; the size-budget
  gate is expected to land green-except-these-6 once the owner-surface Phases
  close.

Every extraction preserves the public API and observable behavior exactly
(cohesive-chunk relocation, not a rewrite); no calculation, CLI, or storage
semantics change as a result of this plan.

## Steps

### Phase `P01` - Inventory and ownership split

Record the 12 size-budget-gate offenders (6 modules, 6 callables) and split them into owner-surface-stable targets to refactor now versus peer-churning targets to defer to their owning campaigns.

- [x] `P01.S01` - Record the 6 over-budget module offenders and their owning campaign (secure_objects.py owner-surface, _iva_ledger.py prorrata, _calendar.py owner-surface, _commands.py mcp, _ledger_bindings.py prorrata, _models.py prorrata); `src/aeat/tests/test_codebase_size_budgets.py`.
- [x] `P01.S02` - Record the 6 over-budget callable offenders and their owning campaign (_classify_iva_transaction prorrata, build_overview_calendar owner-surface, taxpayer_profile_from_mapping owner-surface, ledger_add prorrata, build_server mcp, _call_tool mcp); `src/aeat/tests/test_codebase_size_budgets.py`.
- [x] `P01.S03` - Confirm via git log and git diff that each owner-surface target has no uncommitted peer WIP before refactoring; `src/aeat/application/overview/_calendar.py; src/aeat/domain/deadlines/_profiles.py; src/aeat/adapters/persistence/storage/sql/secure_objects.py`.

### Phase `P02` - Extract application/overview/_calendar.py under budget

Split the module and its over-budget build_overview_calendar callable into cohesive pieces, preserving the public API and behavior exactly.

- [x] `P02.S04` - RAG-ground the calendar module concept, read _calendar.py in full, and identify a cohesive extraction boundary (e.g. per-modelo or per-section calendar builders) that shrinks both the module and build_overview_calendar under their overrides; `src/aeat/application/overview/_calendar.py`.
- [x] `P02.S05` - Extract the identified cohesive chunk into a new sibling module and re-wire build_overview_calendar to call it, preserving the public API and behavior exactly; `src/aeat/application/overview/_calendar.py; src/aeat/application/overview/_calendar_sections.py`.
- [x] `P02.S06` - Run the overview test suite, ruff, pytest --collect-only, and test_codebase_size_budgets to confirm the module and callable are under budget with zero behavior drift; `src/aeat/application/overview/tests/`.

### Phase `P03` - Extract domain/deadlines/_profiles.py:taxpayer_profile_from_mapping under budget

Split the over-budget mapping-to-profile constructor into cohesive helper functions, preserving behavior exactly.

- [x] `P03.S07` - Read taxpayer_profile_from_mapping in full and identify a cohesive extraction boundary (e.g. per-axis mapping helpers) that shrinks it under its override; `src/aeat/domain/deadlines/_profiles.py`.
- [x] `P03.S08` - Extract the identified cohesive chunk into private helper functions in the same module, preserving the public API and behavior exactly; `src/aeat/domain/deadlines/_profiles.py`.
- [x] `P03.S09` - Run the deadlines test suite, ruff, pytest --collect-only, and test_codebase_size_budgets to confirm the callable is under budget with zero behavior drift; `src/aeat/domain/deadlines/tests/`.

### Phase `P04` - Extract adapters/persistence/storage/sql/secure_objects.py under budget

Split the module into cohesive pieces once the secure-persistence campaign confirms the file is quiet, preserving the public API and behavior exactly.

- [x] `P04.S10` - Confirm via git log that secure_objects.py has no uncommitted or actively landing peer WIP from the secure-persistence campaign before starting; `src/aeat/adapters/persistence/storage/sql/secure_objects.py`.
- [x] `P04.S11` - Read secure_objects.py in full and identify a cohesive extraction boundary that shrinks it under its override, preserving the public API and behavior exactly; `src/aeat/adapters/persistence/storage/sql/secure_objects.py`.
- [x] `P04.S12` - Extract the identified cohesive chunk into a sibling module and re-wire callers, preserving the public API and behavior exactly; `src/aeat/adapters/persistence/storage/sql/secure_objects.py`.
- [x] `P04.S13` - Run the storage roundtrip test suite, ruff, pytest --collect-only, and test_codebase_size_budgets to confirm the module is under budget with zero behavior drift; `src/aeat/adapters/persistence/storage/sql/tests/`.

### Phase `P05` - Track deferred peer-owned offenders

Record the 6 peer-churning offenders deferred to the prorrata and mcp campaigns, so the gate's green-except-peer state is documented rather than silently accepted.

- [x] `P05.S14` - Record _iva_ledger.py, _classify_iva_transaction, _ledger_bindings.py, _models.py, and ledger_add as deferred to the prorrata campaign (peer-hot files under active churn) with no code changes made; `src/aeat/application/aggregation/_iva_ledger.py; src/aeat/domain/calculations/registry/_ledger_bindings.py; src/aeat/domain/transactions/_models.py; src/aeat/entrypoints/cli/_ledger.py`.
- [x] `P05.S15` - Record _commands.py, build_server, and _call_tool as deferred to the mcp campaign (peer-hot files under active churn) with no code changes made; `src/aeat/application/wizard/_commands.py; src/aeat/entrypoints/mcp/_server.py`.
- [x] `P05.S16` - Confirm test_codebase_size_budgets fails only on the 6 deferred peer-owned offenders after the owner-surface Phases land, and record this green-except-peer state; `src/aeat/tests/test_codebase_size_budgets.py`.

## Parallelization

P01 (inventory) runs first and is a documentation-only prerequisite for P02-P04. P02 (`_calendar.py`, this agent), P03 (`_profiles.py`), and P04 (`secure_objects.py`) touch disjoint files and carry no interdependency, so they may run fully in parallel across agents (coder-registry takes P02, coder-perf takes P03/P04 per the team lead's split). P05 is a closing documentation Phase and runs after P02-P04 land, once the gate's residual failure set can be confirmed.

## Verification

The plan is complete when every Step is closed (`- [x]`) and
`test_codebase_size_budgets.py` fails only on the 6 deferred peer-owned
offenders named in P05 (zero owner-surface offenders remaining). Each of P02,
P03, and P04 additionally requires: the affected domain's test suite passes,
`pytest --collect-only` is clean, `ruff` is clean, and the target
module/callable is confirmed under its override via
`test_codebase_size_budgets.py` in isolation. Each Phase carries its own
reviewer-gate before being considered closed; a fresh-context honesty review
runs at campaign close per `aeat-campaign-close-honesty-review`.
