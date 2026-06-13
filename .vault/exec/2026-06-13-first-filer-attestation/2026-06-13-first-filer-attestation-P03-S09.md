---
tags:
  - '#exec'
  - '#first-filer-attestation'
date: '2026-06-13'
modified: '2026-06-13'
step_id: 'S09'
related:
  - "[[2026-06-13-first-filer-attestation-plan]]"
---




# Thread workflow_profile.activity_start_date from the verification-action caller into _cross_period_clean_state_verdict_for_work_unit and onward to evaluate_cross_period_clean_state, reusing the exact field the deadline engine consumes

## Scope

- `src/aeat/application/modelo/_verification_actions.py`

## Description

- Thread `workflow_profile.activity_start_date` from `verify_modelo_revision` and the file/export gate (`_require_cross_period_clean_state`, called from `_export.py` and `_filing_actions.py`) through `_cross_period_clean_state_verdict_for_work_unit` into `evaluate_cross_period_clean_state`.
- Reuse the exact `TaxpayerProfile.activity_start_date` field the deadline engine consumes.

## Outcome

- Landed in commit `5d6549183`. All three live entrypoints (verify, export, file) now scope pre-activity dependencies. Verified by the P04.S16 verify-gate tests and the 24 pre-existing gate/enforcement tests staying green.

## Notes

- The verification caller already threaded the `TaxpayerProfile`; this reuses that precedent.
