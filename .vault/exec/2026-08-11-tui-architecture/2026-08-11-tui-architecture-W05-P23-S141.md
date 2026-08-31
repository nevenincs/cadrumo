---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:d2a7de836b72681a08a9f0a4a351609135dbf8770e5d022b7262629f3d83242f'
step_id: 'S141'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Define OperationTransientFinancialOperandProtocolV1 with typed declaration, requirement, submission, access-grant, delivery, acknowledgement, release, expiry, refusal, and broker contracts that are distinct from EphemeralSecretSubmission and persistent secure-reference flows and prohibit operand hashing or durable derivatives

## Scope

- `src/cadrumo/application/operations/_financial_operand.py`

## Changes

- `A` `src/cadrumo/application/operations/_financial_operand.py`
- `A` `src/cadrumo/application/operations/tests/test_financial_operand.py`
- `M` `.vault/plan/2026-08-11-tui-architecture-plan.md`
- `verify:` `uv run --no-sync pytest src/cadrumo/application/operations/tests/test_financial_operand.py -n0` -> `pass`

## Notes

The operand value is a call argument on the ports and a field on no record, so
no shape in this contract can serialize, log or persist an amount. Hashing is
refused structurally rather than by convention: a digest of an amount over a
declared scale inverts by enumeration, so it is a stored amount in disguise.
Both structural gates were proved to bite by adding an `amount_digest` field
and observing the suite red, then restoring.
