---
tags:
  - '#exec'
  - '#legal-grounding-centralization'
date: '2026-06-14'
modified: '2026-06-15'
step_id: 'S01'
related:
  - "[[2026-06-14-legal-grounding-centralization-plan]]"
---




# F6: promote LIRPF art.58/59 family thresholds (max-age 25, max-age 3, custodia 0.5) to external_constants grounded on the cited articles

## Scope

- `src/aeat/domain/contribuyente/family.py`

## Description

- Add three Art. 58/59 LIRPF leaf constants to `core.external_constants`:
  `MINIMO_DESCENDIENTE_MAX_AGE = 25` (art. 58.1), `MINIMO_MENOR_TRES_MAX_AGE = 3`
  (art. 58.3), `CUSTODIA_COMPARTIDA_PRORRATA_FACTOR = Decimal("0.5")` (art. 59), each
  with a binding-provision docstring citing Ley 35/2006 (BOE-A-2006-20764).
- Rewire `domain/contribuyente/family.py`: the module-private `_MAX_AGE_ORDINARY` /
  `_MAX_AGE_MENOR_TRES` now alias the central constants (internal call sites at the
  eligibility predicates unchanged), and `custodia_compartida_prorrata_factor` returns
  the central `CUSTODIA_COMPARTIDA_PRORRATA_FACTOR` instead of an inline `Decimal("0.5")`.

## Outcome

Value-identical centralization (25 / 3 / 0.5 unchanged). Verified the aliases resolve
to the central constants; `ruff` clean; 249 tests pass across
`domain/contribuyente/tests/` and `core/tests/test_external_constants_centralisation_part2.py`.
F6 closed.

## Notes

Pure-centralization move with no value change, so no new oracle was required; existing
behavior tests cover the eligibility and prorrata paths. The `external_constants`
leaf-constant mechanism is the rule-sanctioned home for these by-name regulatory
values, alongside the existing deducción-maternidad family constants.
