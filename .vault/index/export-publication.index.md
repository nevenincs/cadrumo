---
generated: true
tags:
  - '#index'
  - '#export-publication'
date: '2026-08-16'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:9054ed5560e3cdf33378b63a247d82fff90296354496b029add70299d0e5fbb0'
related:
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
- `2026-07-17-export-publication-S12` - Wire the built crash-recovery reconciliation into the production publication path so a crashed export's orphan operation journal and its cleartext staged temporary file are cleared by an operator-reachable code path rather than only by the test harness, choosing the trigger from how the journal and staged temp are actually keyed
- `2026-07-17-export-publication-S13` - Make the personal-data category derivation exhaustive by construction so a new portable-bundle schema field cannot silently vanish from the subject-access disclosure, classifying every bundle field as category-mapped, envelope metadata, or carried-namespace derived and refusing an unclassified field, gated on a non-tautological test that enumerates the model's own fields and proves an unmapped field fails
- `2026-07-17-export-publication-S14` - Isolate each operation inside the export reconciliation sweep so one unreadable or unfinalisable journal cannot starve every later-ordered operation, returning a typed reconciliation that reports the isolated failures rather than swallowing them, gated on a poisoned-journal test proving a healthy operation still reconciles alongside a failing one
- `2026-07-17-export-publication-S15` - Expose an operator-invocable export reconciliation verb under the app root so a crashed operator who never exports again can still clear the orphan journal and its cleartext staged temporary file, reporting cleared and failed operations through the typed notice channel, gated on a crash-simulating test driven through the CLI runner
- `2026-07-17-export-publication-S16` - Close the pre-journal crash window so no cleartext bundle can exist on disk without a journal entry naming it, recording the durable operation before staging rather than after, and extending orphan removal to the hardened writer's own inner temporary file whose name the current suffix guard rejects, gated on a hard-killed child crashing inside the widened window with no cleartext surviving
- `2026-07-17-export-publication-S17` - Make the subject-access completeness claim true by deriving the excluded personal-data categories from the bundle coverage manifest, carrying them beside the included categories through the operation journal and the operator payload, and rewriting the catalogue notice to state both what the archive holds and what it omits, gated on a test asserting the excluded set matches the manifest
- `2026-07-17-export-publication-S18` - Surface the reconciliation failures the pre-flight sweep discards so the export path an operator actually takes reports a leftover journal that may still describe cleartext bytes, carrying them on the export result and emitting them as a warning notice, gated on a test proving the export envelope warns when a journal cannot be reconciled
- `2026-07-17-export-publication-S19` - Classify a journal that vanished mid-scan as a skip rather than a failure so a peer process completing normally cannot make the sweep tell an operator that an unencrypted file may remain, gated on a test removing a journal between scan and reconcile

### plan

- `2026-07-17-export-publication-plan` - `export-publication` plan
