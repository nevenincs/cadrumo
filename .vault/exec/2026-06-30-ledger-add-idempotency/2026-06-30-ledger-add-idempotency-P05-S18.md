---
tags:
  - '#exec'
  - '#ledger-add-idempotency'
date: '2026-06-30'
modified: '2026-07-08'
step_id: 'S18'
related:
  - "[[2026-06-30-ledger-add-idempotency-plan]]"
---

# Add a strict VerificationReport save-load-equality roundtrip plus anti-tautology proof with run_at populated non-default and the outcome-pinned id enforced

## Scope

- `src/aeat/domain/modelos/tests/`

## Description

- Add two domain identity-proof tests to `test_verification_report_roundtrip.py`: two reports differing only in `run_at` derive the same id (clock-free), and a changed findings tuple derives a distinct id.
- The existing strict save-load-equality roundtrip (`_populated_report` carries a non-default `run_at` and a populated findings tuple) plus the flipped-grant anti-tautology proof remain green against the outcome-pinned derivation.

## Outcome

Landed in commit `6ee60da17`. The outcome-pinned, validator-enforced id is proven independent of the wall clock; the encrypted roundtrip + anti-tautology boundary proofs hold under the new identity.

## Notes

`run_at` is the non-identity last-seen field exercised non-default by the roundtrip fixture, satisfying the anti-tautology populate-every-defaultable-field discipline.
