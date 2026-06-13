---
tags:
  - "#exec"
  - "#cross-domain-continuity"
date: 2026-05-27
modified: '2026-05-27'
step_id: S75
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# cross-domain-continuity P19.S75 — predicate evaluator + required-casilla gate

## Outcome

Extended `_required_input_casillas_for_revision` and `_classify_verification_outcome`
in `src/aeat/application/modelo/_actions.py` to honour `CasillaDefinition.required`
(Layer 1) and evaluate `VerificationPredicateDefinition` tuples via a minimal DSL
(`all_nonzero`, `any_nonzero`) (Layer 2).

Functions shipped:
- `_evaluate_predicate_expression(expression, casilla_values)` — evaluates `all_nonzero([ids])` / `any_nonzero([ids])` DSL expressions; unknown expressions pass through without blocking.
- `_evaluate_verification_predicates(predicates, casilla_values)` — loops predicates, calls `_evaluate_predicate_expression`, emits `BLOCKING_RULE` findings on failure.
- `_verification_predicates_for_revision(snap)` — extracts predicates from the registry snapshot.

Both functions wired into `_collect_revision_verification_findings` at the verify path.

Unit tests in `src/aeat/application/modelo/test_verification_substance.py` cover all DSL branches including the pass-through for unknown expressions.

## Files changed

- `src/aeat/application/modelo/_actions.py` (predicate evaluator + Layer 1 integration)
- `src/aeat/application/modelo/test_verification_substance.py` (10 unit tests for S75)
