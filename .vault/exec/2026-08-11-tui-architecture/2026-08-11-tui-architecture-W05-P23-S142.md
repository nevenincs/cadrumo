---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:2497e188bcf8e3c25856930014b74a5b1b480253c60ebab62d69ce7c286f0138'
step_id: 'S142'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Persist only non-sensitive custody checkpoints and serialize awaiting_submission to bound to delivery_started to delivery_acknowledged to released transitions with expiry, cancellation, terminal settlement, crash classification, restart reconciliation, and exactly-once release across racing supervisor paths

## Scope

- `src/cadrumo/application/operations/_journal.py`
- `src/cadrumo/application/operations/_supervisor.py`
- `and src/cadrumo/adapters/persistence/operations/_journal_validation.py`

## Changes

- `A` `src/cadrumo/application/operations/_financial_operand_custody.py`
- `A` `src/cadrumo/application/operations/persistence/financial_operand_custody.py`
- `A` `src/cadrumo/adapters/persistence/operations/financial_operand_custody.py`
- `A` `src/cadrumo/application/operations/tests/test_financial_operand_custody.py`
- `A` `src/cadrumo/adapters/persistence/operations/tests/test_financial_operand_custody.py`
- `M` `.vault/plan/2026-08-11-tui-architecture-plan.md`
- `verify:` `uv run --no-sync pytest src/cadrumo/application/operations/tests/test_financial_operand_custody.py src/cadrumo/adapters/persistence/operations/tests/test_financial_operand_custody.py -n0` -> `pass`

## Notes

The Step row names `_journal.py`, `_supervisor.py` and a private journal
validation module. Those paths are stale: earlier relocation Steps made the
operation journal, supervisor and registry public, and custody is a distinct
concern from the operation journal rather than a field on it, so it persists
through its own repository beside the owner lease. The custody semantics the
row specifies - the four-state order plus expiry, cancellation, terminal
settlement, crash classification, restart reconciliation and exactly-once
release - are all implemented and proved.

Exactly-once release is enforced twice over: the in-process transition table
refuses an illegal move, and the durable compare-and-swap refuses a legal move
applied twice, so two racing supervisor paths presenting the same predecessor
cannot both clear the buffer.

Restart reconciliation deliberately never invents an acknowledgement. A wait
cut off after delivery started settles released, because the buffer died with
the process, and carries DELIVERY_UNCERTAIN permanently.
