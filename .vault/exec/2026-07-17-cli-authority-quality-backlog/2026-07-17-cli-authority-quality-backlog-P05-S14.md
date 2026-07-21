---
tags:
  - '#exec'
  - '#cli-authority-quality-backlog'
date: '2026-07-17'
modified: '2026-07-19'
step_id: 'S14'
related:
  - "[[2026-07-17-cli-authority-quality-backlog-plan]]"
---

# Define typed LLM review requests, decisions, results, and mandatory invocation origins without an application-layer default CLI source command

## Scope

- `src/cadrumo/application/ledger/_llm_review_workflow.py`

## Description

- Create the net-new typed spine module `application/ledger/_llm_review_workflow.py`.
- Define `LlmReviewInvocationOrigin` (StrEnum) as the mandatory operator-intent provenance, with a total origin-to-CLI-spelling map exposed via a derived `source_command` property so the audit label can never be silently blank.
- Define `LlmReviewDecision` (StrEnum) terminals: suggest, apply, reject, split, no_split.
- Define `LlmReviewRequest` (frozen pydantic model) carrying a REQUIRED `invocation_origin` (no default), the decision, subject ids, actor, and reason; its `source_command` is derived from the origin.
- Define the `LlmReviewResult` durable-outcome union over the existing canonical result models (`ManualLedgerTransactionResult`, `LLMSuggestionRejectionResult`, `LLMSplitApplyResult`, `OperatorIvaDerivationResult`); non-persisting suggest previews are excluded as they are inputs to a later decision, not terminal results.
- Add contract tests proving origin->source_command totality/distinctness, distinct auto-split vs split-llm origins, request rejects a missing origin, derived source_command, and frozen-model immutability.

## Outcome

- The mandatory-invocation-origin spine removes, BY DESIGN, the scattered application-layer `source_command="aeat app ledger classify --llm ..."` CLI defaults the existing decision primitives carry: provenance is now a required typed origin from which the CLI spelling is derived data.
- Net-new module, no behavioural change (nothing consumes it yet; the workflow S15 and CLI cutover S16 follow). 6 contract tests pass; ruff and ty green.
- Committed as `3a74b1f0a7`.

## Notes

- Followed the existing LLM-subsystem enum precedent (`LLMProvider` lives application-local in `_llm_suggestions.py`, not core), so the invocation-origin enum is application-local alongside the workflow it governs rather than in core.
- S15 (the workflow composing the ledger persistence primitives), S16 (CLI cutover removing distributed branching + the app-layer defaults), and S17 (real-persistence + real-subprocess integration tests) remain open and build on this vocabulary. Facade promotion to `application.ledger.__all__` is deferred to S16 when the entrypoints CLI consumes these types cross-package (promotion-before-consuming-change discipline).
