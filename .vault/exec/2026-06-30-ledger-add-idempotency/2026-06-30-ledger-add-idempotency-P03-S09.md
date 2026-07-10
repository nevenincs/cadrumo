---
tags:
  - '#exec'
  - '#ledger-add-idempotency'
date: '2026-06-30'
modified: '2026-07-08'
step_id: 'S09'
related:
  - "[[2026-06-30-ledger-add-idempotency-plan]]"
---

# Update the VerificationReport model validator to re-check the new outcome-pinned id derivation and retain run_at as a non-identity last-seen body field

## Scope

- `src/aeat/domain/modelos/_verification_report.py`

## Description

- Update the `VerificationReport` model validator to re-derive the id from the new outcome inputs (`completeness_status`, `findings`) instead of `run_at`, so no report can carry an id inconsistent with its outcome.
- Retain `run_at` as a required non-identity body field (last-seen timestamp); the granted-vs-completeness and disjoint-casilla invariants are unchanged.

## Outcome

Landed in commit `e67b8d7cb`. The validator enforces the outcome-pinned id on construction; the existing anti-tautology proof (flipped-grant) and roundtrip test pass against the new derivation.

## Notes

Co-committed with `S08` and `S10`.
