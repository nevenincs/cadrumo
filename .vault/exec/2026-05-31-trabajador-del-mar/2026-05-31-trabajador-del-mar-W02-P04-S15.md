---
step_id: "S15"
tags:
  - "#exec"
  - "#trabajador-del-mar"
date: "2026-05-31"
modified: '2026-05-31'
related:
  - "[[2026-05-31-trabajador-del-mar-plan]]"
  - "[[2026-05-31-trabajador-del-mar-adr]]"
---

# trabajador-del-mar W02.P04.S15 step record

## Step

Implement RETMAR mandatory-filing status check raising ProfileCompletenessError (not a calculation gate) when retmar_registered=True.

## Files Touched

- `src/aeat/domain/renta/_maritime_exemption.py` — check_retmar_mandatory_filing function; raises ProfileCompletenessError when retmar_registered=True. Error carries context={legal_ref: "Ley 47/2015 BOE-A-2015-11346"}.
- `src/aeat/core/errors/registry/_domain.py` — registered ProfileCompletenessError as ERROR_RENTA_PROFILE_COMPLETENESS_WARNING.

Note: The plan specified `ProfileCompletenessWarning` but ruff N818 requires the `Error` suffix for exception classes. The class was renamed to `ProfileCompletenessError` throughout.

## Commit

`2a210aff1` — feat(renta/maritime): W02.P03-P04 binding selectors + exemption calculations

## BOE Citations

- Ley 47/2015 BOE-A-2015-11346 — RETMAR mandatory filing since January 2023 for all registered workers regardless of income level

## Outcome

ProfileCompletenessError raised when retmar_registered=True. Gate is non-blocking (callers catch, surface to operator, continue processing). Does not alter casilla values or formula paths.
