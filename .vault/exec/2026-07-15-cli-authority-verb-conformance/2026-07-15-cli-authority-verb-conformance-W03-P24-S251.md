---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S251'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Implement one application review workflow for suggest, saturate, review, apply, reject, evidence no-split, and evidence split while composing existing canonical persistence primitives

## Scope

- `src/cadrumo/application/ledger/_llm_review_workflow.py`
- `src/cadrumo/application/ledger/_llm_classification.py`
- `src/cadrumo/application/ledger/__init__.py`

## Description

- Read the shipped review workflow and check each of the seven named intents against a real dispatch branch.
- Confirm the workflow introduces no write path of its own and delegates to the canonical ledger persistence primitives.
- Confirm the package facade exports the workflow so consumers bind to the public surface rather than a private module.

## Outcome

Already satisfied. Closed as verified rather than re-implemented.

`execute_reviewed_decision` is the single persisting decision terminal, and each branch delegates rather than writes. Reject routes to `reject_llm_suggestion`; apply discriminates on the suggestion type, routing a saturated suggestion to `apply_saturated_llm_classification` and a stage-one classification to `apply_llm_classification`; split routes to `apply_evidence_split`. The repository handles and clock override are forwarded verbatim, so injected persistence and deterministic time still reach the primitive that owns the write. No catalogue save, event build, or secure-write batch appears in the workflow module itself, which is what composing rather than re-implementing has to mean here.

The two non-persisting terminals are handled as contract rather than omission. Suggest and no-split cannot reach the dispatch, and passing either raises with the decision and origin in the error context. A decision and suggestion shape mismatch, such as a split decision on a classification suggestion, raises rather than silently falling through to a wrong primitive. That closes the branch space: every combination either delegates or refuses.

The seven named intents map onto this surface without a gap. Suggest and no-split are the refusing terminals, review is the dispatch itself, and apply, saturate, reject and evidence split each have a delegating branch. Evidence split and the auto-split route share one branch while carrying different origins, which is the intended arrangement rather than a collapse of the two operator intents.

The package facade exports `LlmReviewDecision`, `LlmReviewInvocationOrigin` and `execute_reviewed_decision` through the ledger `__init__`, so the CLI binds to the public top-level surface.

No change was needed or made.

## Notes

Semantic CODE search is degraded and reports itself healthy, so the workflow and its primitives were confirmed by direct read and targeted grep rather than by search. A search miss was treated as no evidence.

This step's action text is word-for-word identical to a step in the sibling quality-backlog plan, which is closed. That step cites only the workflow module, while this one also cites the classification module and the package facade; reading all three is what confirms the delegation is real rather than asserted in a docstring.
