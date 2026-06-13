---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: 2026-05-27
modified: '2026-05-27'
step_id: S377
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-05-27-dsl-conditional-predicate-adr]]"
---

# `cross-domain-continuity` `W04.P19.S377`

Add the runtime evaluation branch for the `implies_nonzero` predicate so the verification phase of a modelo calculate run can apply the conditional rule.

Commit: `0303316fe`

- Modified: `src/aeat/application/modelo/_actions.py`

## Description

Added `_PREDICATE_IMPLIES_NONZERO` regex (`^implies_nonzero\(\[(?P<ids>[^\]]*)\]\)$`) and the matching evaluation branch inside `_evaluate_predicate_expression`. The branch parses the comma-separated id list, retrieves antecedent and consequent values via the standard `.get(id, Decimal(0))` default-zero convention, and returns:

- `True` (predicate holds) when the antecedent is `<= 0`. Mirrors the AEAT phrasing "cuando C01 sea positivo" — a non-positive antecedent does not engage the implication.
- `True` when the consequent is non-zero. The happy-path satisfaction case.
- `False` (predicate violated) when the antecedent is strictly positive AND the consequent is zero or missing.
- `True` when the id list is malformed (length != 2). Mirrors the defensive contract of `cap_le_when_positive`; registry-side validation is the typo gate.

The operator extends the docstring on `_evaluate_predicate_expression` so callers see the new shape alongside the existing three. The docstring also clarifies that unknown predicates do not block the operator — the authoring-time validator under `_validate_surfaces.py` is the typo gate.

## Verification

- Unit tests authored at S378 cover all five branches (antecedent zero, antecedent negative, both positive, consequent zero, consequent missing).
- The runtime branch only activates when the registry register from S376 admits the operator name, so the two leaves are functionally coupled.

## Gate evidence

- G1 no naked env reads: unchanged.
- G2 typed pydantic at boundary: predicate values are `Mapping[str, Decimal]` per the surrounding shape; no widening.
- G3 user messages via tr(): N/A; engine-internal branch.
- G4 no locale yml hand-edits: unchanged.
- G5 no shims: branch mirrors the existing three operators' decoding pattern.
- G6 no tautological tests: implementation only; tests at S378.

## References

- ADR: dsl-conditional-predicate-adr (D2 contract for the implication semantics)
- Sibling Steps: S376 (registry register), S378 (test suite)
- Surface: `_evaluate_predicate_expression` at `src/aeat/application/modelo/_actions.py:2342`; regex constant at `:2321`.
