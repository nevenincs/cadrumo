---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:679b167ef384e85a006bad39b172d9ebda73fcc98d7cb56d8a77ecbdb9e88d6e'
step_id: 'S141'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

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
