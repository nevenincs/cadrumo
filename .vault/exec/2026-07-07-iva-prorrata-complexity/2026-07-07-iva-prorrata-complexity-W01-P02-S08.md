---
tags:
  - '#exec'
  - '#iva-prorrata-complexity'
date: '2026-07-07'
modified: '2026-07-08'
step_id: 'S08'
related:
  - "[[2026-07-07-iva-prorrata-complexity-plan]]"
---

# Implement the last-three-active-years global seed walk (summed volumes via compute_prorrata_definitiva_anual, skipping the gap) and the insufficient-history advisory

## Scope

- `src/aeat/domain/prorrata_register/__init__.py`
- `src/aeat/application/calculations/_prorrata_regularizacion.py`

## Description

- Add the domain walk `ProrrataRegister.collect_last_three_active_years` and the `ThreeActiveYearsAggregate` carrier: walk the register backward from the target ejercicio, skip interrupted and unsettled years, sum the con-derecho/sin-derecho volume inputs of the last three ACTIVE años naturales, and report whether a full three contributed.
- Add the application seed `build_interrumpida_tres_ultimos_seed` and its `ProrrataInterruptedSeed` carrier: when three active years exist, compute the GLOBAL definitive percentage over the summed volumes via `compute_prorrata_definitiva_anual` and stamp it `INTERRUMPIDA_TRES_ULTIMOS`; when fewer exist, return an unresolved seed plus a visible insufficient-history advisory naming the found years.
- Add domain walk tests (skips the gap, takes the last three active years, skips unsettled years, reports insufficient history).

## Outcome

- Modified files: `src/aeat/domain/prorrata_register/__init__.py`, `src/aeat/application/calculations/_prorrata_regularizacion.py`, `src/aeat/domain/prorrata_register/tests/test_prorrata_register.py`.
- 53 domain + application prorrata tests pass; ruff / ruff-format / ty clean.
- Committed atomically with this exec record and the plan step check.

## Notes

- Layering respected: the domain register owns the walk (aggregate the volumes); the application seed consumes the compute substrate `compute_prorrata_definitiva_anual` over the summed volumes, per the register module's stated boundary (settlement compute lives in the application layer).
- The rule is a GLOBAL percentage over AGGREGATE volumes, never the average of the three definitive percentages, and over the last three ACTIVE años (skipping the gap), never the three calendar years - the two failure modes the ADR calls out; the S09 oracle proves both.
- Insufficient history surfaces an advisory rather than assuming a percentage (no-silent-under-declaration).
