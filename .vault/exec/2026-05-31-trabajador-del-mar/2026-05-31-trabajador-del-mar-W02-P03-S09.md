---
step_id: "S09"
tags:
  - "#exec"
  - "#trabajador-del-mar"
date: "2026-05-31"
modified: '2026-06-29'
related:
  - "[[2026-05-31-trabajador-del-mar-plan]]"
  - "[[2026-05-31-trabajador-del-mar-adr]]"
---

# trabajador-del-mar W02.P03.S09 step record

## Step

Add rebeca_eligible predicate to the binding selector (vessel_registry == REBECA OR scheduled_canary_route).

## Files Touched

- `src/aeat/domain/renta/_maritime_exemption.py` — rebeca_eligible predicate; covers REBECA, rebeca_eu_eea (2021 EU/EEA extension per Art. 75.1), and scheduled_canary_route values.

## Commit

`2a210aff1` — feat(renta/maritime): W02.P03-P04 binding selectors + exemption calculations

## BOE Citations

- Ley 19/1994 Art. 73.2 BOE-A-1994-15794 — REBECA 50% exemption base condition
- Ley 19/1994 Art. 73.3 BOE-A-1994-15794 — crew employment contract and vessel enrollment requirements
- Ley 19/1994 Art. 75.1 BOE-A-1994-15794 — extension to EU/EEA sister-registry vessels since 1 January 2021
- Ley 19/1994 Art. 75.3 BOE-A-1994-15794 — employer-side Modelo 111 withholding base adjustment

## Outcome

rebeca_eligible returns True for vessel_registry in {REBECA, rebeca_eu_eea, scheduled_canary_route} when worker_class=trabajador_del_mar.
