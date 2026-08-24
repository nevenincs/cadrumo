---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-13'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:64ce15f8e0600216eff4cf81cb09159db8cea209556eed9ae2fdaacfcbe9acc5'
step_id: 'S86'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---
# Replace the remaining transaction-model free-form recovery hints

## Scope

- `src/cadrumo/domain/transactions/_models.py`
- `src/cadrumo/domain/transactions/tests/test_gross_invariant.py`

## Description

Removed residual IRPF/category instructions and ledger-category command prose from gross-mismatch validation while retaining the authoritative arithmetic invariant.

## Outcome

- Rent, professional, and incoming mismatch branches emit no independently authored recovery guidance.
- Recovery is not fabricated at this domain-model invariant; operator projection remains a boundary concern.
- All three branch tests assert the arithmetic invariant and reject reintroduction of `aeat`, `irpf_category`, or `ledger categories` prose.
- Verification: focused gross-invariant suite — 33 passed; ruff clean.
- Independent review: PASS.

## Notes

This closes the exact live residue found by the plan reconciliation; it does not claim unrelated transaction behavior.
