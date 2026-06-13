---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: 2026-05-27
modified: '2026-05-27'
step_id: S376
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-05-27-dsl-conditional-predicate-adr]]"
---

# `cross-domain-continuity` `W04.P19.S376`

Register the `implies_nonzero` verification-predicate operator name on the registry-side closed catalogue so registry-level validation accepts it without falling back to the unknown-operator path.

Commit: `2abb0a6c6`

- Modified: `src/aeat/domain/calculations/registry/_schema.py`

## Description

Authored the registry-layer half of the new conditional DSL predicate. The closed `KNOWN_VERIFICATION_PREDICATE_OPERATORS` frozenset on `_schema.py` (line 2068) gains the `implies_nonzero` token. The constant is the authoring-time gate that registry validation consults before letting a predicate expression through; without the token the operator name would be rejected even though the runtime branch (S377) recognises it. The frozenset shape (NOT a tuple) is intentional — membership tests are O(1) on the validate-surface hot path.

The docstring at the operator-list comment is updated to enumerate the four predicate shapes the catalogue admits: `all_nonzero`, `any_nonzero`, `cap_le_when_positive`, `advisory_when_ratio_ge`, plus the new `implies_nonzero`.

## Verification

- Registry-schema test suite continues to load the schema module cleanly; no test added at this leaf (the test surface lands at S378).
- The frozenset construction is part of module import; an authoring typo would fail every registry validate run on import — implicit gate.

## Gate evidence

- G1 no naked env reads: unchanged.
- G2 typed pydantic at boundary: predicate descriptor unchanged; this Step only widens the operator-name catalogue.
- G3 user messages via tr(): N/A; constant authoring.
- G4 no locale yml hand-edits: unchanged.
- G5 no shims: unchanged.
- G6 no tautological tests: no test changes at this leaf.

## References

- ADR: dsl-conditional-predicate-adr (canonical authority for the operator's semantics)
- Sibling Steps: S377 (runtime branch), S378 (test suite)
- Surface: `KNOWN_VERIFICATION_PREDICATE_OPERATORS` at `src/aeat/domain/calculations/registry/_schema.py:2068`
