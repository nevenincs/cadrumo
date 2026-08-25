---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:9a8a7287fd9293d0e8da19de234104ba2c3b65da30d6e219fb97df29003e1448'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
  - "[[2026-08-24-tui-registry-api-gate-adr]]"
  - "[[2026-08-25-tui-architecture-s160-approved-amendment-architecture-review-audit]]"
---

# `tui-architecture` audit: `S171 plan-only defining-module review`

## Scope

Independent plan-only review of commit `880016ef8c4` against the accepted
canonical defining-module amendment and the approved Workspace architecture
remediation packet. The review covered S128, S129, S163, S165, S167, S171,
S172, and S173, plus the S160/S174 dependency boundary, assertion-axis,
typed-refusal, epoch-digest, cursor, owner, deletion, direct-import, and
ordering requirements. No plan or source file was changed.

S163, S165, S167, and S173 name unambiguous public owners; S174 alone owns the
pure two-axis evaluator; S171 owns the strict model shape and typed mismatch;
S128 owns public assembly; and the epoch-v2 comparison domain and identical
`contributor_epoch_digest` binding across baseline, bounded facets, and typed
cursors are coherent. The finding below prevents an overall pass.

## Findings

### atomic-package-binding-cutover | high | S171 and S172 defer part of their hard moves to S129

The accepted amendment requires each former private definition, every consumer,
the old module, and its package export to move or disappear in one atomic
commit. S171 and S172 hard-move `_workspace_models.py` and
`_workspace_producers.py`, respectively, and require direct consumer imports,
but S129 later claims deletion of every `application.modelo` package binding.
That split leaves the executor to choose between retaining a forbidden
re-export after the defining-module move, silently pulling S129 work forward,
or repeating deletion ownership. S129 is therefore not an unambiguous genuine
residual cutover, and the relocation rows do not state the accepted atomic
boundary.

## Recommendations

FAIL. Amend S171 to delete every Workspace-model package binding and gate the
inert `application.modelo` namespace in the same commit as the model move.
Amend S172 identically for every producer-contract/registration binding. Remove
package-binding deletion from S129 and narrow it to the true current-HEAD
residual: direct-import cutover for remaining assembly/dispatch, frontend, and
receipt consumers not already owned by S171/S172, followed by inert-namespace,
definition-module, and zero-remnant fixed-point proof. Retain the explicit
prohibition on repeating the S171, S172, or S128 moves.

