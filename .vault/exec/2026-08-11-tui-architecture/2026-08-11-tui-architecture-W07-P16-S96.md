---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:75297357c440e1a909a225a64b32644edcdb6c10789cc8dc613499f21bdb5682'
step_id: 'S96'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Crash and restart recorded and resumable operations to prove lease takeover, cursor replay, resume policy, and orphan reporting

## Scope

- `src/cadrumo/application/operations/tests/test_restart_reconciliation.py`

## Changes

- `A` `src/cadrumo/application/operations/tests/test_restart_reconciliation.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/application/operations/tests/test_restart_reconciliation.py -m integration -n0 -q` -> `pass`

## Notes

Discovery for this Step ran against the local fallback search index, not the live
semantic-search service, which was down for the session. Absence of a result in that
index is therefore not evidence that no such code exists; every claim about what does
or does not exist in the tree was confirmed by direct search of the source rather than
by the index alone.

GAP, reported and deliberately not built here: operand custody restart reconciliation
has no caller on the live path. The broker's restart reconciliation method has exactly
one occurrence in the tree, its own definition, and the supervisor's reconcile path
never invokes it. This Step proves the supervisor's restart reconciliation and cannot
prove operand custody restart, because nothing wires it. Building that wire inside a
test Step would have hidden a production gap behind a passing test.

Three registry constraints surfaced while building, each a real limit on how any
future crash or restart test can be written. A credential-free request type must
explicitly inherit the credential-free request base; a plain model is refused at
definition build. A definition carrying a review interaction must declare a public
review projection schema or the registry refuses. And the definition contract digest
is pinned at submission, so an owner recovering under a different reconciliation
policy is refused for contract drift: the first draft of this Step crashed under one
policy and recovered under another, which silently proved drift refusal, already
covered elsewhere, instead of restart reconciliation. Both owners must pin the same
contract.

The definition and executor are test-declared; lease takeover, cursor replay, resume
policy evaluation, checkpoint re-entry, orphan classification and interrupt settlement
are production, exercised across a real process boundary after the first owner is
killed outright.
