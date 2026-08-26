---
tags:
  - '#exec'
  - '#cli-root-verb-homes'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:07ca5537293a6f156b78f4d274961ce85c5486ef65f182b15efb2bb0b48734fc'
step_id: 'S59'
related:
  - "[[2026-08-26-cli-root-verb-homes-plan]]"
---

# RULED: `destructive` means irreversible, so `ledger stash` moves onto the same non-destructive policy `archive` and `restore` already use

## Scope

- `src/cadrumo/entrypoints/cli/`

## Changes

- `M` `src/cadrumo/entrypoints/cli/_app_ledger_lifecycle_command_specs.py`
- `verify:` `python -c "...COMMAND_GRAPH policy.destructive..."` -> `archive False, stash False, restore False, remove True, reset True`
- `verify:` `pytest four campaign gates + test_command_policy.py` -> `22 passed`
- `verify:` `pytest test_command_policy.py test_app_ledger_command_specs.py -m integration` -> `pass`
- `verify:` `python -c "...graph..."` -> `294 leaves, 64 declarations`

## Notes

`app ledger stash` declared `destructive=True` while `app ledger archive`
declared `False`, and nothing in the tree said which was right.
`TransactionLifecycleState` documents ARCHIVED and STASHED as equally
reversible, both verbs demand `--yes`, both carry the identical option set
(`reason`, `yes`, `actor`), and `restore` returns a row from either state. The
two declarations could not both be correct.

The flag has no prose definition anywhere in the codebase -- only structural
validation, that a destructive command must carry the `local-state` side effect
-- so its meaning was set by usage, and the usage contradicted itself. Since the
value is projected into the operator-facing command schema, the reading was put
to the operator rather than chosen here. The ruling: `destructive` means the
operation cannot be reversed. `remove` deletes, `reset` destroys review state,
and those stay true; the three lifecycle moves do not.

The fix was not a flag flip. `_POLICY_9` is shared by `remove`, `reset` and
`stash`, so editing it would have changed all three. `stash` now uses
`_POLICY_4`, which is what `archive` and `restore` already use and which differs
from `_POLICY_9` in the `destructive` field alone -- same capabilities, same
side effects, same performance class, same write route. Nothing but the
declaration moved.

Found by reading the same-subject scan that produced S58, from the policy column
rather than the help column.
