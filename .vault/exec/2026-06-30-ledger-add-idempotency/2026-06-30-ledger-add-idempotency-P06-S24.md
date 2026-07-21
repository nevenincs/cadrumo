---
tags:
  - '#exec'
  - '#ledger-add-idempotency'
date: '2026-06-30'
modified: '2026-07-08'
step_id: 'S24'
related:
  - "[[2026-06-30-ledger-add-idempotency-plan]]"
---

# Add a strict ModeloRecord save-load-equality roundtrip plus anti-tautology proof with filed_at populated non-default and the outcome-pinned id enforced by the model validator

## Scope

- `src/aeat/domain/modelos/tests/`

## Description

- Add a clock-free / outcome-pinned identity proof: two `ModeloRecord` instances differing only in `filed_at` share one `filing_record_id` (validator accepts both), and a different actor diverges the id.
- Add an outcome-pinned-id anti-tautology: a `ModeloRecord` whose id was derived for a different actor than it carries is refused by the model validator, with `filed_at` populated non-default to confirm it never participates in the id.

## Outcome

Landed in commit `cdad9bc22`; the filing-record roundtrip suite is 15 green. The existing strict encrypted save-load-equality roundtrip (`_populated_catalogue` carries non-default `filed_at`, notes, external evidence, supersession) and the supersession-chain anti-tautology remain green under the outcome-pinned identity.

## Notes

The pre-existing roundtrip fixture already satisfies the populate-every-defaultable-field discipline; this step adds the identity-contract proofs the id change introduces.
