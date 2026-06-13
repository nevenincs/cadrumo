---
tags:
  - '#exec'
  - '#first-filer-attestation'
date: '2026-06-13'
modified: '2026-06-13'
step_id: 'S11'
related:
  - "[[2026-06-13-first-filer-attestation-plan]]"
---




# Fail closed with a blocking finding that prompts the operator to record the activity-start date when the profile carries no activity_start_date at all, so the gate never silently opens

## Scope

- `src/aeat/application/modelo/_verification_actions.py`

## Description

- Emit `_cross_period_missing_activity_start_finding`: a BLOCKING finding prompting the operator to record the activity-start date when an evidence-missing dependency blocks AND the profile carries no `activity_start_date` at all.
- Gate the fail-closed finding on a curated `_FIRST_FILER_CANDIDATE_BLOCKERS` set so non-first-filer flows with clean cross-period verdicts are unaffected.

## Outcome

- Landed in commit `5d6549183`. The gate fails closed instructively rather than silently opening. Proven by P04.S16 `test_verify_fails_closed_when_profile_records_no_activity_start_date`.

## Notes

- Fires only when an evidence-missing dependency a genuine first filer would hit blocks; a clean verdict never triggers it, so existing flows do not regress.
