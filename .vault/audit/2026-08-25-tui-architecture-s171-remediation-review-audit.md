---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:9b65e255bb9e435204eb6ac93ebefbd6ecd13de4f25ac5a676b868a26100df44'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
  - "[[2026-08-25-tui-architecture-s171-code-review-audit]]"
  - "[[2026-08-11-tui-architecture-W03-P20-S171]]"
---

# `tui-architecture` audit: `S171 Workspace model relocation remediation review`

## Scope

Independent formal remediation review of `W03.P20.S171` against the accepted
Workspace architecture decision, the amended plan, the frozen plan-review and
code-review audits, and the execution record. The review rechecked the completed
cursor-coordinate finding and the current implementation at committed HEAD
`5a6538df6ad`; it did not change source, tests, the plan, the execution record,
the registry, or either frozen prior audit.

The public defining module, direct consumers, inert package boundary, strict
assertion axes, typed mismatch refusal, epoch-digest binding, complete cursor
coordinate, unavailable-facet rule, and strict round trips conform at the
reviewed tree. The original three focused S171 integration lanes are green with
36 tests: 22 Workspace-model tests, 6 producer-contract tests, and 8 manifest
tests. The later committed cursor-coordinate matrix is green as well,
completing the prior reviewer finding on behavior and proof.

## Findings

### s171-contract | pass | Current Workspace model implementation conforms

At the reviewed HEAD, `workspace_models.py` is the sole public defining module;
the retired private module and API-document target are absent from the active
tree, and the `application.modelo` package carries no Workspace-model binding.
The model validates both fixed-source revision assertion axes, preserves every
evaluated axis in typed mismatch refusal, and requires one identical
`contributor_epoch_digest` across the baseline, bounded facet, and cursor. The
cursor validator checks contract version, selected revision, schema identity,
facet, and digest; page-state and unavailable-facet rules are fail-closed. The
36-test focused baseline and the later cursor-coordinate matrix cover the
current contract and completed reviewer proof. No behavioral or structural
code finding remains.

### s171-relocation-atomicity | medium | The hard move was delivered across two commits

The relocation was not atomic in the sense required by S171. Commit
`3ec3f7908a` renamed the source and API-stub paths while five source/test
consumers, the root API document, and the drift disposition still named the
retired `_workspace_models` surface. Commit `1d13b76fbea` later converged those
consumers and metadata and carried the S171 execution record. The final tree is
clean and the implementation conforms, but the exact S171 row cannot be
certified as an atomic hard move from the surviving history. Merging or rewriting
those shared commits would be unsafe and is not an authorised remediation.

## Recommendations

Do not mutate S171 plan state or invoke a plan check/closure in this review;
leave the frozen plan, execution record, and prior audits untouched. Treat
`s171-relocation-atomicity` as a durable
historical carry-forward: do not rewrite shared history, revert peer work, or
create a cosmetic replacement commit that pretends the move was atomic. Future
relocations should use an ownership-verified path-scoped landing with the full
consumer and documentation inventory staged together, while preserving every
intermediate importable state.

Final disposition: **PASS** for the current implementation and focused proof;
**NOT CERTIFIED** for S171 lifecycle closure because the historical atomicity
claim cannot be made from the existing commits without an unsafe history rewrite.
