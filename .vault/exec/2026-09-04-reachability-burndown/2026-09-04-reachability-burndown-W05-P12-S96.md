---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:94b7ed869065b71944b7bf9926a2cc9c96a80cc02a2613ef5a86c1e9482b3046'
step_id: 'S96'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Gate the class the escaso-valor threshold belonged to: every constant in the external-constants file is either referenced by shipped code or carries a ledger entry saying why it is not, since a legally grounded figure sitting among enforced ones reads as enforced and no other gate sees the difference. Sweep the file first, finding eight unapplied constants and all eight already adjudicated, so the gate starts green over a real population rather than a repaired one.

## Scope

- `dev/audit/tests/test_external_constants_are_applied_or_adjudicated.py`

## Changes

- `A` `dev/audit/tests/test_external_constants_are_applied_or_adjudicated.py`
- `verify:` `pytest .../test_external_constants_are_applied_or_adjudicated.py`
  6 passed
- `verify:` teeth proved against the LIVE file -- appending an unreferenced
  constant fails the gate; restored and re-verified
- `verify:` module ratchet, secure-store gate and docstring ratchet exit 0;
  duplication 10 / 0.05%; dead code 0; unused 1033, exact 404
- `verify:` `ruff check` and `ty check` clean

## Notes

The rule is a disjunction and both halves are honest outcomes: a constant is
either referenced by shipped code, meaning the product applies it, or it carries
a ledger entry saying why it does not yet. What is refused is the third state, a
figure with neither, which asserts an enforcement nobody performs. No other gate
sees that: the constant imports, and every test of the file passes.

The sweep found eight unapplied constants and all eight already adjudicated --
the maternity-deduction set, two thresholds, the BOE encoding choices and the
escaso-valor figure closed last step. So the gate starts green over a real
population of sixty-three rather than over a population I had just repaired,
which is the difference between a gate and a ratchet on my own work.

A first draft reported FOURTEEN unapplied, and the six false ones taught the
detector rule worth keeping: `from x import RATE as _RATE` binds `_RATE` while
REFERENCING `RATE`, so recording only the bound name hides every aliased
consumer. Six of the fourteen were aliased at their single call site. The scan
now records both halves of an alias, and one of the teeth cases pins that
behaviour so it cannot regress.

This is the fourth distinct detector bug this campaign, and they rhyme: each
came from a resolution rule that is right for the common shape and silently
wrong for one the codebase actually uses.
