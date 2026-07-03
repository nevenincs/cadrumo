---
step_id: "S16"
tags:
  - "#exec"
  - "#trabajador-del-mar"
date: "2026-05-31"
modified: '2026-06-29'
related:
  - "[[2026-05-31-trabajador-del-mar-plan]]"
  - "[[2026-05-31-trabajador-del-mar-adr]]"
---

# trabajador-del-mar W02.P04.S16 step record

## Step

Write calculation tests using registry-authoritative fixture values for Art. 7.p) and REBECA; verify CasillaObservation.legal_refs populated end-to-end.

## Files Touched

- `src/aeat/domain/renta/test_maritime_exemption.py` — TestCalculateArt7pExemption (12 cases) and TestCalculateRebecaExemption (8 cases). All expected values derived from statutory formula and cap, not from model runtime output.

## Commit

`2a210aff1` — feat(renta/maritime): W02.P03-P04 binding selectors + exemption calculations

## BOE Citations

- Ley 35/2006 Art. 7.p) BOE-A-2006-20764 — cap 60,100 EUR; formula annual_salary/365*qualifying_days
- Ley 19/1994 Arts. 73.2 73.3 75.1 75.3 BOE-A-1994-15794 — fraction 0.50

## Outcome

W02 close gate roundtrip test: CasillaObservation.legal_refs carries "Ley 35/2006 Art. 7.p) BOE-A-2006-20764" for Art. 7.p) and "BOE-A-1994-15794" for REBECA. source_refs carry "art-7p-foreign-work" and "rebeca-50pct" respectively. 107 total tests pass.
