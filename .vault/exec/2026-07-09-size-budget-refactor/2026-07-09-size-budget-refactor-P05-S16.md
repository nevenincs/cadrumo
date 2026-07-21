---
tags:
  - '#exec'
  - '#size-budget-refactor'
date: '2026-07-09'
modified: '2026-07-09'
step_id: 'S16'
related:
  - "[[2026-07-09-size-budget-refactor-plan]]"
---

# Confirm test_codebase_size_budgets fails only on the 6 deferred peer-owned offenders after the owner-surface Phases land, and record this green-except-peer state

## Scope

- `src/aeat/tests/test_codebase_size_budgets.py`

## Description

- Confirmed all three owner-surface Phases landed: P02 `_calendar.py` (this campaign's coder-registry slice, `43c95b0b7d`), P03 `_profiles.py:taxpayer_profile_from_mapping` (coder-perf, `ccd5e2057`), P04 `secure_objects.py` (coder-perf, `93303b177`).
- Re-ran `test_codebase_size_budgets.py` at campaign close.
- Confirmed the gate now fails on exactly the deferred set and nothing else: 4 module-line offenders (`_iva_ledger.py`, `_ledger_bindings.py`, `_models.py`, `_commands.py`) and 4 callable-line offenders (`_classify_iva_transaction` in `_iva_ledger.py`, `ledger_add` in `_ledger.py`, `build_server` and `_call_tool` in `_server.py`) -- 8 offender entries across 6 distinct files (the plan's originally-estimated "6 offenders" undercounted because `_iva_ledger.py` and `_server.py` each trip both the module-line and the callable-line gate).
- Confirmed zero owner-surface offenders remain in either offender list.

## Outcome

Green-except-peer state confirmed and recorded: `test_codebase_size_budgets.py` fails only on the 8 offender entries (across 6 distinct files) owned by the prorrata and mcp campaigns, exactly matching P05.S14/S15's inventory. Zero owner-surface offenders remain.

## Notes

The plan's Description/P05 intent text said "6 offenders"; the precise count is 6 distinct files producing 8 offender entries across the two gate axes, recorded accurately here rather than silently matching the earlier estimate.
