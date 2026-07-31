---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:035442fad661112f01089adf34c4d55d9093d52158c202868b38128e711ed63e'
step_id: 'S252'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Route classify --auto-split and split --llm through the typed review workflow with distinct invocation origins and remove CLI-owned review branching and application source-command defaults

## Scope

- `src/cadrumo/entrypoints/cli/_ledger_llm_cli.py`
- `src/cadrumo/entrypoints/cli/_ledger_lifecycle_cli.py`

## Description

- Locate both CLI routes and confirm each reaches the typed workflow rather than a primitive directly.
- Confirm the two routes carry different invocation origins.
- Check the remaining direct-primitive call site in the LLM CLI and judge whether it is surviving review branching.

## Outcome

Already satisfied. Closed as verified rather than re-implemented.

Both routes reach the shared workflow, and they are in different modules. The `classify --auto-split` route calls `execute_reviewed_decision` from the LLM CLI module with `CLASSIFY_AUTO_SPLIT` and a split decision. The `split --llm` route calls the same function from the lifecycle CLI module with `SPLIT_LLM` and a split decision. The two origins are distinct members deriving distinct audit labels, so the two operator intents stay separately attributable while sharing one code path, which is what the governing decision record asks for. The apply and saturate-apply routes likewise dispatch through the workflow under their own origins, and the reject helper takes the origin as a parameter from its callers rather than choosing one itself.

The CLI retains only what it should. In the split routes the preview branch renders and returns before any decision is taken, so the branching that survives is presentation, not review policy: the durable decision is made once, inside the workflow.

One call site does not go through `execute_reviewed_decision`. The `--iva-category --saturate` route calls `derive_operator_iva_substrate` directly. This is not surviving review branching. That route derives an IVA substrate from an operator-supplied category with no model suggestion to approve or decline, so it has no review decision to route and sits outside the suggest-review-decide loop this workflow owns. It nonetheless takes its audit label from the `CLASSIFY_IVA_CATEGORY_SATURATE` origin rather than a literal, so the enum remains the single declaration of that label. Treating it as a violation would have meant inventing a review decision for an invocation that has none.

No application source-command default remained on either cited route. The one surviving default elsewhere in the package is recorded against S250.

No change was needed or made to either cited module.

## Notes

Semantic CODE search is degraded and reports itself healthy, so both routes were located by direct read and confirmed with targeted grep across the CLI package.

The sibling quality-backlog step with identical wording cites only the LLM CLI module. The `split --llm` route lives in the lifecycle CLI module, which only this step cites, so the sibling's closure did not by itself establish that the second route was converted. Reading it was the substance of this check, and it is converted.
