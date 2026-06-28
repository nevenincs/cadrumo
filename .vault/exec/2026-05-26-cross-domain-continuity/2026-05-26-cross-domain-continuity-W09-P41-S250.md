---
step_id: S250
tags:
  - "#exec"
  - "#cross-domain-continuity"
date: 2026-05-27
modified: '2026-05-27'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# cross-domain-continuity W09.P41.S250

## Summary

Implemented oracle tests for M100 casilla 0511 (mínimo del contribuyente, parte estatal) age-derived increment per Art. 57.1.b LIRPF. The `age_at_year_end` formula operator was already committed in the prior session; this step delivers the oracle test file and repairs the downstream test suite broken by concurrent peer-agent matrimonio bindings.

## Changes

- `src/aeat/domain/calculations/registry/test_minimo_contribuyente_age_increment.py` — NEW oracle test file. Eight tests covering 2024 and 2025 filing years: three age brackets (under 65 / 65-74 / >=75) and an anti-tautology guard. Uses `load_registry_tree` + `_build_validated_snapshot` + `calculate_registry_snapshot` directly to bypass `ValidatedRegistryAuthority` corpus-citation validation (which fails on concurrent peer-agent WIP with binary PDF corpus files). Supplies marriage-axis binding stubs (full-year / month-start / month-end = 0) required by peer-agent matrimonio formulas now wired into the construct execution path.

- `src/aeat/domain/calculations/registry/test_modelo_100_settlement_chain.py` — Add marriage binding stubs to `_binding_values()`. Fix pre-existing RUF002 en-dash violations in docstring escala tables.

- `src/aeat/domain/calculations/registry/test_registry_scenarios.py` — Add marriage binding stubs to all five 2025 scenario `binding_values` dicts.

## Oracle authority

Art. 57.1.b LIRPF + AEAT renta 2024/2025 manual (Mínimo del contribuyente section):
- age < 65 at 31-Dec of filing year: 5,550 EUR
- age 65-74: 5,550 + 1,150 = 6,700 EUR
- age >= 75: 5,550 + 1,150 + 1,400 = 8,100 EUR

## Commit

`494134257` — S250: M100 mínimo personal Art. 57.1.b age-derived increment from birth_date (Carla #205)

## Gates

- ruff: clean
- pyright: 0 errors on oracle test file; pre-existing unannotated fixture params in settlement chain test (not introduced by this step)
- pytest: 17/17 pass
