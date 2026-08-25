---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:43c9ff46fa9d4a917fec1ee5e2f7ef8184f9f0501b3210a93c658d93df214e17'
step_id: 'S102'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---

# Migrate IVA-compensation exception producers to typed catalogue/live-input verdicts or explicit terminal/no-recovery dispositions

## Scope

- `src/cadrumo/domain/iva_compensation/_carry_forward.py`
- `src/cadrumo/domain/iva_compensation/_reconciliation.py`

## Description

- Migrate the wallet reconciliation input refusals and the reconciliation invariant guard to their registered keys.
- Migrate the carry-forward expiry and quarter-ordinal refusals to the registered filing-calculate key.
- Carry the mismatched identity, target, bound and source period as machine facts.

## Outcome

- The declared package carries no operator-facing prose refusal; a rescan returns only pydantic model invariants, which are programmer-error guards rather than operator refusals.
- Every migration reused a key already registered against its error class, so no new locale leaf was required in any catalogue.
- The mismatch refusals now name both sides as facts rather than asserting disagreement in a sentence: the wallet's target year and period beside the snapshot's.
- The package suite passes thirty-four tests serially and is lint clean.

## Notes

- Executed file by file with a test run between each.
- Consumer verification was scoped to the owning package. The wider modelo wallet-gate suites carry pre-existing failures in wallet seeding that predate this step and were observed early in the campaign session; they concern the seeding gate rather than the reconciliation or carry-forward producers migrated here, and no touched path appears in their tracebacks.
- No carry-forward.
