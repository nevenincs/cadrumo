---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:8d20ddd2c1e9ca8e9c32b70edb1302af5650f245f43d2cbdaf66b656a33e5472'
step_id: 'S148'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Run the sole Edit Contract dependency validator against the exact green Workspace C2 and financial-operand receipts, accepted edit authority, closed EditContract implementation tuple, enrolled production definition, guarded result evidence, current source tree, no-legacy proof, and duplicate-authority census

## Scope

- `src/cadrumo/application/modelo/tests/test_edit_dependency_receipt.py`

## Changes

- `M` `src/cadrumo/application/modelo/tests/test_edit_dependency_receipt.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/application/modelo/tests/test_edit_dependency_receipt.py -m unit -n0` -> `pass`

## Notes

The validator already existed; this Step ran it and re-derived the one proof
whose premise had changed. Its predecessor assertion was written to fail
exactly once, when the required Workspace C2 receipt was minted, and it fired
as designed.

The predecessor proof was strengthened beyond a straight re-derivation. The
existing branch recorded the predecessor's path as its evidence, which would
have made the proof that a dependency is satisfied the filename. The
derivation now parses the predecessor and requires a `PASSED` verdict for the
expected receipt schema, so a red or reshaped predecessor breaks it.

The predecessor was repointed to the CLI-scaffolded document. Two receipts
for that subject existed, carrying the same schema and validator and both
green, at divergent commits; the hand-named one is not a form the owning verb
produces. The superseded copy was left in place for its owner to retire.

The first negative test written here was tautological: it re-read the same
document and re-asserted what the derivation asserts, so it could not fail.
It was replaced with a pure checker exercised against four corrupted inputs
-- red verdict, foreign schema, missing head commit, non-document.

The `NOT_APPLICABLE` arm was kept rather than deleted, with its trigger
pointed the other way, so a withdrawn predecessor falls back to it instead of
the field silently disappearing. The self-invalidating discipline survives
rather than being consumed by its own firing.

Discovery ran on grep and direct file reads rather than the semantic search
service, which was unavailable. The tree's import state broke and recovered
three times during this Step, and this module was uncollectable for part of
it.
