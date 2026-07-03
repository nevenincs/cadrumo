---
step_id: "S13"
tags:
  - "#exec"
  - "#trabajador-del-mar"
date: "2026-05-31"
modified: '2026-06-29'
related:
  - "[[2026-05-31-trabajador-del-mar-plan]]"
  - "[[2026-05-31-trabajador-del-mar-adr]]"
---

# trabajador-del-mar W02.P04.S13 step record

## Step

Implement REBECA calculation (exempt_amount = gross_navigation_income * Decimal(0.50)), output as CasillaObservation with legal_refs from registry binding.

## Files Touched

- `src/aeat/domain/renta/_maritime_exemption.py` — calculate_rebeca_exemption function; produces CasillaObservation targeting casilla 0525 with legal_refs from all four Ley 19/1994 articles and source_refs=("rebeca-50pct",).

## Commit

`2a210aff1` — feat(renta/maritime): W02.P03-P04 binding selectors + exemption calculations

## BOE Citations

- Ley 19/1994 Art. 73.2 BOE-A-1994-15794 — 50% exemption base condition
- Ley 19/1994 Art. 73.3 BOE-A-1994-15794 — REBECA vessel and employment requirements
- Ley 19/1994 Art. 75.1 BOE-A-1994-15794 — EU/EEA extension since 1 January 2021
- Ley 19/1994 Art. 75.3 BOE-A-1994-15794 — employer Modelo 111 withholding base adjustment

## Outcome

calculate_rebeca_exemption returns CasillaObservation with value = gross_navigation_income * 0.50. The 50% fraction is statutory and not variable by election. Covers REBECA, rebeca_eu_eea, and scheduled_canary_route variants.
