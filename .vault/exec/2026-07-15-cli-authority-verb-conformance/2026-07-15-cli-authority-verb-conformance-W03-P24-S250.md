---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S250'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Define typed LLM review requests, decisions, results, and mandatory invocation origins without an application-layer default CLI source command

## Scope

- `src/cadrumo/application/ledger/_llm_review_workflow.py`
- `src/cadrumo/application/ledger/_llm_suggestions.py`

## Description

- Establish that this step duplicates a step already closed under a sibling backlog plan.
- Read the shipped review-workflow vocabulary and confirm it against the step's own wording rather than its docstring.
- Audit the whole application ledger package for a surviving defaulted CLI source command, which is the prohibition this step carries.
- Remove the one surviving default and pin every caller to an explicit label.

## Outcome

Already satisfied in its main clause; one residual instance of its prohibition was found and fixed.

The typed vocabulary exists and is substantial. `LlmReviewInvocationOrigin` is a six-member `StrEnum` whose values are CLI-spelling-independent tokens, and the operator-facing audit label is derived through a `source_command` property backed by a module-level mapping that is total over the enum, so a new origin without a spelling raises at first use rather than producing a blank label. `LlmReviewDecision` names the five terminals, with `SUGGEST` and `NO_SPLIT` explicitly non-persisting. `LlmReviewRequest` is strict and frozen, carries `invocation_origin` with no default, and re-derives its own `source_command` from that origin. The result contract is a named union of the already-canonical ledger result models, and the module comment states why non-persisting previews are deliberately excluded from it.

The mandatory-origin requirement holds at the boundary that matters: all six `source_command` parameters on the ledger LLM persistence primitives are keyword-only with no default, so a caller cannot reach a durable write without naming its origin.

The prohibition, though, was not fully honoured. `split_transaction_with_classified_children` still declared `source_command: str = "aeat app ledger classify --read-evidence --auto-split --apply"`. That is an application-layer default naming a CLI command, and it is a second declaration of the exact label `CLASSIFY_AUTO_SPLIT` now owns, so editing the enum would have left the two silently disagreeing. It sits on the LLM split path, since `apply_evidence_split` composes it. The default was unreachable in production because the only production caller already passed the argument explicitly, so removing it is behaviour-preserving; one refusal test relied on the default and now passes the label explicitly. After the change the invocation-origin enum is the sole declaration of that audit label.

Committed in `003a2f987d`.

## Notes

Semantic CODE search is degraded and reports itself healthy. A probe naming ledger LLM classification and review returned five hits from an unrelated censo manager-actions module, and none of the LLM modules appeared. Every module in this step was therefore located by direct read and confirmed with targeted grep, and a search miss was treated as no evidence at all.

The step cites the review-workflow and suggestions modules, but the defect its own wording prohibits lived in neither: it was in the split/merge action module. This is the same citation drift already recorded for S246 in this campaign, and it is now the second confirmed instance rather than a coincidence. An auditor reading the plan rows alone would have declared this step clean.
