---
step_id: "S14"
tags:
  - "#exec"
  - "#trabajador-del-mar"
date: "2026-05-31"
modified: '2026-05-31'
related:
  - "[[2026-05-31-trabajador-del-mar-plan]]"
  - "[[2026-05-31-trabajador-del-mar-adr]]"
---

# trabajador-del-mar W02.P04.S14 step record

## Step

Implement DA 41 guard raising MaritimeExemptionInactiveError if da41_eligible resolves True.

## Files Touched

- `src/aeat/domain/renta/_maritime_exemption.py` — guard_da41_inactive function; raises MaritimeExemptionInactiveError with full BOE context when da41_eligible is True. Error carries context={binding_id, legal_ref, enabling_law}.
- `src/aeat/core/errors/registry/_domain.py` — registered MaritimeExemptionInactiveError as REFUSED_RENTA_MARITIME_EXEMPTION_INACTIVE.

## Commit

`2a210aff1` — feat(renta/maritime): W02.P03-P04 binding selectors + exemption calculations

## BOE Citations

- Ley 35/2006 DA 41 BOE-A-2006-20764 — EU state-aid clearance requirement, not granted as of 2024/2025
- Ley 6/2018 BOE-A-2018-9268 — enabling amendment

## Outcome

DA 41 guard tested with TestGuardDa41Inactive. MaritimeExemptionInactiveError raised when da41_eligible returns True. Error context carries both legal_ref and enabling_law for operator-facing diagnosis.
