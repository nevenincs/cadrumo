---
tags:
  - '#exec'
  - '#ledger-add-idempotency'
date: '2026-06-30'
modified: '2026-07-08'
step_id: 'S08'
related:
  - "[[2026-06-30-ledger-add-idempotency-plan]]"
---

# Change derive_verification_report_id to fold the verification outcome of calculation_revision_id, completeness_status, the findings tuple, and verified_by, and drop run_at from the identity

## Scope

- `src/aeat/domain/modelos/_verification_report.py`

## Description

- Rewrite `derive_verification_report_id` to fold the verification outcome - `calculation_revision_id`, `completeness_status`, the ordered `findings` tuple (each `model_dump(mode="json")`, list order preserved by the canonical-JSON serialiser), and `verified_by` - and drop `run_at` from the hashed payload.
- Update the module and `VerificationReport` docstrings to state the identity is the outcome and `run_at` is a non-identity last-seen field.

## Outcome

Landed in commit `e67b8d7cb`. The report id is now clock-free; two identical-outcome verify runs derive the same id (collapse on upsert) while a changed-finding re-verify derives a distinct id.

## Notes

Co-committed with `S09` and `S10`: a pydantic id-validator and its derivation are inseparable (the ADR Constraints section mandates moving them together), and a signature change must update every call site in one green tree.
