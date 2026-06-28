---
step_id: "S08"
tags:
  - "#exec"
  - "#trabajador-del-mar"
date: "2026-05-31"
modified: '2026-05-31'
related:
  - "[[2026-05-31-trabajador-del-mar-plan]]"
  - "[[2026-05-31-trabajador-del-mar-adr]]"
---

# trabajador-del-mar W02.P03.S08 step record

## Step

Add art_7p_eligible predicate to the binding selector (vessel_flag != ES AND waters_type == international).

## Files Touched

- `src/aeat/domain/renta/_maritime_exemption.py` — new module; art_7p_eligible predicate (S08), rebeca_eligible predicate (S09), da41_eligible predicate (S10), selector unit tests covered in S11 step.
- `src/aeat/domain/renta/__init__.py` — re-exports maritime exemption public surface.
- `src/aeat/domain/renta/errors.py` — added `__all__`.
- `src/aeat/core/errors/registry/_domain.py` — registered MaritimeExemptionInactiveError and ProfileCompletenessError error codes.

Note: S08-S11 were implemented as a cohesive unit in a single module and commit; this record covers S08 specifically (art_7p_eligible predicate).

## Commit

`2a210aff1` — feat(renta/maritime): W02.P03-P04 binding selectors + exemption calculations

## BOE Citations

- Ley 35/2006 Art. 7.p) BOE-A-2006-20764 — Art. 7.p) conditions: work outside Spanish territory, foreign entity, equivalent income tax or CDI. International waters qualify per TEAR Galicia December 2024 and Supreme Court doctrine April 2025.

## Outcome

art_7p_eligible returns True when worker_class=trabajador_del_mar AND (vessel_flag=foreign OR waters_type=international). Returns False for all non-maritime worker profiles.
