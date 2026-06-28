---
step_id: "S11"
tags:
  - "#exec"
  - "#trabajador-del-mar"
date: "2026-05-31"
modified: '2026-05-31'
related:
  - "[[2026-05-31-trabajador-del-mar-plan]]"
  - "[[2026-05-31-trabajador-del-mar-adr]]"
---

# trabajador-del-mar W02.P03.S11 step record

## Step

Write selector unit tests covering art_7p_eligible true/false, rebeca_eligible true/false, da41_eligible inactive-guard raises domain error.

## Files Touched

- `src/aeat/domain/renta/test_maritime_exemption.py` — TestArt7pEligible (7 cases), TestRebecaEligible (6 cases), TestDa41Eligible (5 cases), TestGuardDa41Inactive (3 cases including error context assertions).

## Commit

`2a210aff1` — feat(renta/maritime): W02.P03-P04 binding selectors + exemption calculations

## BOE Citations

Per predicate — see S08, S09, S10 records.

## Outcome

All 21 selector tests pass. Guard test asserts MaritimeExemptionInactiveError is raised with correct legal context (legal_ref=Ley 35/2006 DA 41 BOE-A-2006-20764, enabling_law=Ley 6/2018 BOE-A-2018-9268).
