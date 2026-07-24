---
generated: true
tags:
  - '#index'
  - '#export-publication'
date: '2026-07-24'
modified: '2026-07-24'
related:
  - '[[2026-07-17-export-publication-S01]]'
  - '[[2026-07-17-export-publication-S02]]'
  - '[[2026-07-17-export-publication-S03]]'
  - '[[2026-07-17-export-publication-S04]]'
  - '[[2026-07-17-export-publication-S05]]'
  - '[[2026-07-17-export-publication-S06]]'
  - '[[2026-07-17-export-publication-S07]]'
  - '[[2026-07-17-export-publication-S08]]'
  - '[[2026-07-17-export-publication-S09]]'
  - '[[2026-07-17-export-publication-S10]]'
  - '[[2026-07-17-export-publication-S11]]'
  - '[[2026-07-17-export-publication-adr]]'
  - '[[2026-07-17-export-publication-audit]]'
  - '[[2026-07-17-export-publication-plan]]'
  - '[[2026-07-24-export-publication-close-honesty-review-audit]]'
---

# `export-publication` feature index

Auto-generated index of all documents tagged with `#export-publication`.

## Documents

### adr

- `2026-07-17-export-publication-adr` - `export-publication` adr: `export-publication rescope grounding` | (**status:** `accepted`)

### audit

- `2026-07-17-export-publication-audit` - `export-publication` audit: `export durable-layer continuous-gate review`
- `2026-07-24-export-publication-close-honesty-review-audit` - `export-publication` audit: `Close honesty review`

### exec

- `2026-07-17-export-publication-S01` - Define typed portable-transfer and subject-access export purposes, requests, results, target identity, and categories derived from the actual portable bundle schema and carried registered namespaces while keeping sealed recovery archives separate
- `2026-07-17-export-publication-S02` - Persist non-secret profile export operation states atomically outside the target artifact
- `2026-07-17-export-publication-S03` - Implement one locked target serialization with restrictive temporary files, file fsync, durable PREPARED state, atomic replace, parent-directory fsync, post-publish COMPLETED event, and honest PREPARED recovery
- `2026-07-17-export-publication-S04` - Re-export the typed profile export service as the sole public export orchestration API
- `2026-07-17-export-publication-S05` - Prove portable-transfer and subject-access purposes use the same service and bundle schema, derive categories from serialized fields and registry-carried namespaces, and retain distinct purpose metadata
- `2026-07-17-export-publication-S06` - Prove restrictive temporary permissions, same-target exclusion, every PREPARED and replace crash window, parent-directory durability, and fresh-process reconciliation without premature completion events
- `2026-07-17-export-publication-S07` - Route both config profile export and subject-access-request through the sole portable-export application service and remove direct serialization, target writes, completion events, and static SAR category ownership from the CLI
- `2026-07-17-export-publication-S08` - Migrate the export family help, risk, and cleartext handoff-risk metadata to the accepted grammar with equal classification for both purposes
- `2026-07-17-export-publication-S09` - Regenerate the operator reference pages for portable export and subject access from the frozen live surface
- `2026-07-17-export-publication-S10` - Gated requirement surfaced by the export durable-layer review, latent until S07 wires both export doors through the shared service: make reconcile_prepared_exports hold the per-destination lock (or a repository lock spanning staged-temp removal and journal delete) per operation, or guarantee the S07 call site runs reconcile only at exclusive startup, so a reconcile concurrent with a live same-target export cannot unlink the live staged temp and spuriously fail os.replace with a ProfileExportError
- `2026-07-17-export-publication-S11` - Decide and implement whether a crash after os.replace succeeds but before the PROFILE_EXPORTED audit event eventually emits that event: adopt the three-phase journal (PREPARED, then replace plus fsync transitioning to COMPLETED, then emit the event, with reconcile completing a COMPLETED-but-eventless operation), closing the un-audited data-egress window and wiring the currently-dead COMPLETED operation-state enum, a data-egress audit-completeness posture item with limited privacy impact (a local file at the operator own path, not remote transmission), gated on no durably-published bundle lacking a PROFILE_EXPORTED event after reconcile

### plan

- `2026-07-17-export-publication-plan` - `export-publication` plan
