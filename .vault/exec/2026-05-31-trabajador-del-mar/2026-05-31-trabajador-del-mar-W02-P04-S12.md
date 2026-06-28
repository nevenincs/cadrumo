---
step_id: "S12"
tags:
  - "#exec"
  - "#trabajador-del-mar"
date: "2026-05-31"
modified: '2026-05-31'
related:
  - "[[2026-05-31-trabajador-del-mar-plan]]"
  - "[[2026-05-31-trabajador-del-mar-adr]]"
---

# trabajador-del-mar W02.P04.S12 step record

## Step

Implement Art. 7.p) calculation (exempt_amount = min(annual_salary / 365 * qualifying_days, 60100)), output as CasillaObservation with legal_refs from registry binding.

## Files Touched

- `src/aeat/domain/renta/_maritime_exemption.py` — calculate_art_7p_exemption function; produces CasillaObservation targeting casilla 0525 (irpf_rentas_exentas_base_general) with legal_refs=("Ley 35/2006 Art. 7.p) BOE-A-2006-20764",) and source_refs=("art-7p-foreign-work",).

## Commit

`2a210aff1` — feat(renta/maritime): W02.P03-P04 binding selectors + exemption calculations

## BOE Citations

- Ley 35/2006 Art. 7.p) BOE-A-2006-20764 — statutory formula and annual cap 60,100 EUR
- TEAR Galicia December 2024 — confirmation for Galician fishing crew
- Supreme Court April 2025 — extension to military Navy in NATO/UN sea operations

## Outcome

calculate_art_7p_exemption returns CasillaObservation with value = min(salary/365*days, 60100). Cap is enforced. legal_refs and source_refs populated from registry binding entries. Casilla 0525 (rentas_exentas_base_general) is the target per AEAT Modelo 100 dictionary.
