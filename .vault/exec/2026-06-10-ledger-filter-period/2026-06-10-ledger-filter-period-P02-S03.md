---
tags:
  - '#exec'
  - '#ledger-filter-period'
date: '2026-06-12'
step_id: 'S03'
related:
  - "[[2026-06-10-ledger-filter-period-plan]]"
---

# Confirm the four aggregation_period_for_modelo call sites pass canonical StandardPeriodCode tokens via CalculationSourceContext.period

## Scope

- `src/aeat/application/aggregation/_modelo_bindings.py`

## Description

- Audit the live call sites of `aggregation_period_for_modelo` in `_modelo_bindings.py` (now at `:159`, `:255`, `:311` after the typed-`Period` refactor compacted the module to 416 lines).
- Confirm each passes `snapshot.period` / `work_unit.period`, which are canonical `StandardPeriodCode` values, not free-form strings.
- Confirm the translator itself normalises and validates through `Period.from_year_and_code` plus a `has_date_span()` guard, raising `AggregationValidationError` on any non-span token — so no caller-side normalisation is required.

## Outcome

Confirmed at HEAD. Every call site feeds a canonical token; the translator rejects span-less and unknown tokens. Precondition for the P02.S04 alias deletion satisfied — the removed branches read a shape no caller writes.

## Notes

The plan cited line `:448-453` for the alias block and `:158/:251/:304/:383` for call sites; the module was compacted by the parallel typed-`Period` refactor, so the current line numbers differ. The structural facts (canonical tokens at every call site) hold.
