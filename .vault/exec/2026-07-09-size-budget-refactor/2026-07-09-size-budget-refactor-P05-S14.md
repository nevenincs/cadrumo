---
tags:
  - '#exec'
  - '#size-budget-refactor'
date: '2026-07-09'
modified: '2026-07-17'
body_hash: 'sha256:039578fbb7b9771cb5ae7d659e65be0a8accf378e3503a40ecddf3b647bc9f14'
step_id: 'S14'
related:
  - "[[2026-07-09-size-budget-refactor-plan]]"
---

# Record _iva_ledger.py, _classify_iva_transaction, _ledger_bindings.py, _models.py, and ledger_add as deferred to the prorrata campaign (peer-hot files under active churn) with no code changes made

## Scope

- `src/aeat/application/aggregation/_iva_ledger.py`
- `src/aeat/domain/calculations/registry/_ledger_bindings.py`
- `src/aeat/domain/transactions/_models.py`
- `src/aeat/entrypoints/cli/_ledger.py`

## Description

- Confirmed via `git log -1` / `git status` at each check during the campaign that all four files carry active, uncommitted or recently-landing prorrata-campaign commits, consistent with the plan's ADR (`2026-07-09-size-budget-refactor-adr`) ownership split.
- Applied `full-tree-gate-must-distinguish-owner`: touching a shared, red, repository-wide gate's offenders requires triage by ownership before any agent acts; these four are the prorrata campaign's, not this campaign's, to fix.
- Made no code changes to any of the four files under this plan.
- Re-ran `test_codebase_size_budgets.py` at campaign close and confirmed the offenders remain present exactly as recorded: `_iva_ledger.py` (1617 lines > budget 1250), `_ledger_bindings.py` (1440 lines > budget 1400), `_models.py` (1419 lines > budget 1340), and the `_classify_iva_transaction` callable (208 lines > budget 180, inside `_iva_ledger.py`) and `ledger_add` callable (238 lines > budget 198, inside `_ledger.py`).

## Outcome

Four prorrata-owned offenders (3 module-size, 2 callable-size, one module shared between both axes) recorded as deliberately deferred; zero code changes made.

## Notes

No incidents. This Step is a documentation-only tracking action per the plan's design.
