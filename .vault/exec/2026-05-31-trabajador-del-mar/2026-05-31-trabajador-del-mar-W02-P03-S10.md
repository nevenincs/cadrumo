---
step_id: "S10"
tags:
  - "#exec"
  - "#trabajador-del-mar"
date: "2026-05-31"
modified: '2026-05-31'
related:
  - "[[2026-05-31-trabajador-del-mar-plan]]"
  - "[[2026-05-31-trabajador-del-mar-adr]]"
---

# trabajador-del-mar W02.P03.S10 step record

## Step

Add da41_eligible predicate as future/inactive gate (tuna_fleet AND pending_eu_clearance).

## Files Touched

- `src/aeat/domain/renta/_maritime_exemption.py` — da41_eligible predicate returns True when worker_class=trabajador_del_mar AND tuna_fleet=True AND pending_eu_clearance=True. Predicate is separated from the guard function so it can be tested independently.

## Commit

`2a210aff1` — feat(renta/maritime): W02.P03-P04 binding selectors + exemption calculations

## BOE Citations

- Ley 35/2006 DA 41 BOE-A-2006-20764 — DA 41 LIRPF selector: tuna fleet crew, Spanish-flagged, outside EU waters, 200+ nautical miles from baselines
- Ley 6/2018 BOE-A-2018-9268 — enabling amendment that introduced DA 41; conditions EU state-aid clearance not granted as of 2024/2025

## Outcome

da41_eligible predicate implemented as future/inactive gate. Caller code (guard_da41_inactive) raises MaritimeExemptionInactiveError when True, preventing silent production of legally incorrect output.
