---
tags:
  - '#exec'
  - '#unfalsifiable-test-sweep'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:3c44f35d4d84f1903d3cdde4a4139a555c80d3e47aa9ae3b81bb272af6d44585'
step_id: 'S02'
related:
  - "[[2026-08-09-unfalsifiable-test-sweep-plan]]"
---
# Floor the production UTF-8 corpus independently of the ratchet, so draining the backlog cannot remove the only protection

## Scope

- `src/cadrumo/tests/test_utf8_enrollment_inventory.py`

## Description

- Added `test_the_production_corpus_is_not_empty`, asserting the production walk returns more files than a collapse floor.
- Documented on the test why the pre-existing protection was accidental and why it could not be relied on.

## Outcome

**The defect this closes is subtler than a missing floor, and worse.**

The production scan was already protected, but only as a side effect: with 38 live ratchet entries, an empty corpus makes all 38 look vanished, so the inert-entry check fails loudly. That reads like a working guard.

It is self-cancelling. The ratchet exists to be drained - its own failure message instructs the reader to delete entries, and its docstring records the backlog falling from 78 to 38. The protection is therefore strongest when the cleanup has barely begun and disappears at the exact moment it succeeds. A team that finishes the work the ratchet was built to drive would silently convert a working gate into a permanently vacuous one, with no test failing at the moment it happened.

This is not hypothetical. The dev ratchet in the same module has already reached zero, and the dev scan was unfalsifiable in consequence.

The new floor does not depend on the ratchet's contents, so the backlog can now drain to zero without taking the gate with it.

## Verification

    uv run --no-sync pytest src/cadrumo/tests/test_utf8_enrollment_inventory.py -n 0 -q
    5 passed in 4.21s

Mutation simulating the ratchet's own designed success state - backlog fully cleaned - combined with a collapsed walk:

    FAILED test_the_production_corpus_is_not_empty
    1 failed, 4 passed in 1.82s

The inert-entry check PASSES under that mutation, because an empty ratchet has nothing that can be inert. Only the new floor fires. Before this Step that combination was entirely silent.

## Notes

Floor set at 200 against 1553 live files, for the same reason as its dev sibling: it asks whether the walk collapsed, not whether the tree grew.
