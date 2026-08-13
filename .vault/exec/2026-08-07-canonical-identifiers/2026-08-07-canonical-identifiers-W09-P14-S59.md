---
tags:
  - '#exec'
  - '#canonical-identifiers'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:2123571e5ec757f5ee97128a6b7423916105dcd21acf7b560e69ba468507c9ac'
step_id: 'S59'
related:
  - "[[2026-08-07-canonical-identifiers-plan]]"
---

# prove the gate's bite: add a throwaway bare-`str` field named to match the namespace vocabulary on a scratch model outside `src`, confirm the gate reds, then remove it and confirm the gate is green again

## Scope

- `src/cadrumo/tests/test_identifier_namespace_enrollment_gate.py`

## Description

- Write a throwaway pydantic model outside the package tree carrying one bare
  `str` field named to match the namespace vocabulary.
- Drive the gate's own assertion function over the pinned production sources plus
  that scratch model and observe it red, naming the field.
- Remove the scratch model and observe the same assertion green.
- Re-run the committed gate to confirm the restored state.

## Outcome

The bite is proven against the gate's real detector, not a reimplementation of it.
The probe reads the pinned production source set the gate itself scans, appends the
scratch module as one extra source, builds the candidate set through the gate's own
field-walking function and calls the gate's own unledgered-violation assertion.

With the scratch model present the assertion raised, and the failure named the
field, its concept and its state:

```
Identifier-named model fields declared as bare `str` and named by no ledger.
Type each with its core.identity alias, or record it with a stated reason:
  scratch/scratch_model.py:9 ScratchRatchetProbe.expediente_id: str [BARE] token=expediente_id
```

With the scratch model removed the same assertion over the same production sources
returned clean: `no unledgered bare identifier field`. The probe asserts both
outcomes, so it fails if either direction stops holding.

The committed gate was then re-run in full and reported eleven passed, confirming
the restored green state at the revision the gate scans.

The probe additionally lives on inside the gate as a committed assertion, driving
the scanner over an explicit four-field source snapshot: it proves a bare
identifier field is reported, a typed one is not, a truncated display companion is
excluded, and a non-vocabulary field is ignored. Without that, a matcher that
silently stopped matching would let every other assertion in the module pass while
detecting nothing.

## Notes

The Step row mandates the scratch model live outside the package tree, and it did:
the probe and its model were written to a session scratch directory, never under
the package and never tracked. Nothing in the repository was mutated to produce the
red, so no peer sweep could have committed the mutation and a crashed run would
have left no residue. The scratch model was deleted after the proof.

Driving the gate's assertion function directly, rather than running the test binary
against a mutated tree, is what made the out-of-tree form possible at all: the gate
scans a pinned revision of the package, so a scratch file outside it is invisible
to an ordinary run by construction. Feeding the extra source through the same entry
point the gate uses is the only way to exercise the real detector on it, and it is
the shape the sibling censuses already use for their contract tests.

No test double was involved. The scratch model is real input to the real AST
scanner, not a stand-in for it.
