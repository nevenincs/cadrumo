---
tags:
  - '#plan'
  - '#export-publication'
date: '2026-07-17'
modified: '2026-07-17'
tier: L1
related:
  - '[[2026-07-15-cli-authority-verb-conformance-adr]]'
  - '[[2026-07-15-cli-authority-verb-conformance-research]]'
  - '[[2026-07-15-cli-authority-verb-conformance-reference]]'
  - '[[2026-07-16-cli-authority-verb-conformance-duplication-authority-audit]]'
  - '[[2026-07-17-cli-authority-verb-conformance-audit]]'
  - '[[2026-07-15-cli-authority-verb-conformance-plan]]'
  - '[[2026-07-17-export-publication-audit]]'
---

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the
       related: field above.
     - The related: field carries the AUTHORISING documents
       (ADR, research, reference, prior plan) for every Step in
       this plan. Steps inherit this chain; per-row reference
       footers do not exist.
     - NEVER use [[wiki-links]] or markdown links in the
       document body. -->

# `export-publication` plan

- [x] `S01` - Define typed portable-transfer and subject-access export purposes, requests, results, target identity, and categories derived from the actual portable bundle schema and carried registered namespaces while keeping sealed recovery archives separate; `src/cadrumo/application/user_profile/_bundle_export_contracts.py`.
- [x] `S02` - Persist non-secret profile export operation states atomically outside the target artifact; `src/cadrumo/application/user_profile/_bundle_export_operation.py`.
- [x] `S03` - Implement one locked target serialization with restrictive temporary files, file fsync, durable PREPARED state, atomic replace, parent-directory fsync, post-publish COMPLETED event, and honest PREPARED recovery; `src/cadrumo/application/user_profile/_bundle_export.py`.
- [x] `S04` - Re-export the typed profile export service as the sole public export orchestration API; `src/cadrumo/application/user_profile/__init__.py`.
- [x] `S05` - Prove portable-transfer and subject-access purposes use the same service and bundle schema, derive categories from serialized fields and registry-carried namespaces, and retain distinct purpose metadata; `src/cadrumo/application/user_profile/tests/test_bundle_export.py`.
- [x] `S06` - Prove restrictive temporary permissions, same-target exclusion, every PREPARED and replace crash window, parent-directory durability, and fresh-process reconciliation without premature completion events; `src/cadrumo/application/user_profile/tests/test_bundle_export_recovery.py`.
- [ ] `S07` - Route both config profile export and subject-access-request through the sole portable-export application service and remove direct serialization, target writes, completion events, and static SAR category ownership from the CLI; `src/cadrumo/entrypoints/cli/_config/_profile_export.py`.
- [ ] `S08` - Migrate the export family help, risk, and cleartext handoff-risk metadata to the accepted grammar with equal classification for both purposes; `src/cadrumo/application/operator_surface/_risk_table.py`.
- [ ] `S09` - Regenerate the operator reference pages for portable export and subject access from the frozen live surface; `docs/reference/import-export-and-evidence.md`.
- [ ] `S10` - Gated requirement surfaced by the export durable-layer review, latent until S07 wires both export doors through the shared service: make reconcile_prepared_exports hold the per-destination lock (or a repository lock spanning staged-temp removal and journal delete) per operation, or guarantee the S07 call site runs reconcile only at exclusive startup, so a reconcile concurrent with a live same-target export cannot unlink the live staged temp and spuriously fail os.replace with a ProfileExportError; `the gate is a test that holds the destination lock and proves reconcile does not remove the live staged temp or raise a spurious ProfileExportError; `src/cadrumo/application/user_profile/_bundle_export.py, src/cadrumo/application/user_profile/tests/test_bundle_export_recovery.py`.
- [ ] `S11` - Decide and implement whether a crash after os.replace succeeds but before the PROFILE_EXPORTED audit event eventually emits that event: adopt the three-phase journal (PREPARED, then replace plus fsync transitioning to COMPLETED, then emit the event; reconcile completes a COMPLETED-but-eventless operation), closing the un-audited data-egress window and wiring the currently-dead COMPLETED operation-state enum; this is a data-egress audit-completeness posture item with limited privacy impact (a local file at the operator's own path, not remote transmission); the gate is that no durably-published bundle lacks a PROFILE_EXPORTED event after reconcile; `src/cadrumo/application/user_profile/_bundle_export.py, src/cadrumo/application/user_profile/tests/test_bundle_export_recovery.py`.
## Description

Collapse two CLI-owned export writers onto one durable publication service. Portable profile export and the subject-access request each independently implement serialization, directory creation, publication, and event sequencing from inside the CLI. That is two parallel writers for the same durable artifact, each with its own crash behaviour, and neither with a recoverable preparation state.

The accepted authority is one export service carrying portable-transfer and subject-access as typed purposes rather than as separate implementations. It owns same-target locking, recoverable preparation, atomic publication, and schema-derived categories. Categories are derived from the actual bundle schema and the registered namespaces the bundle carries, not from a static list hand-maintained in the CLI that silently drifts from what the bundle actually contains.

Publication is the delicate part. The service serializes to a restrictive temporary file, fsyncs it, records a durable prepared state, atomically replaces the target, fsyncs the parent directory, and only then emits the completion event. A crash in any window recovers honestly: a prepared state that never published is reported as prepared, not as complete, and the completion event never fires for an artifact that was not durably published.

The decision record keeps these purposes distinct while sharing machinery. Portable export and subject-access export have different purposes and different legal discoverability, so their purpose metadata stays distinct even though the publication path is shared. The sealed recovery archive has different confidentiality and restoration semantics and stays entirely separate; it is not folded into this service. Both purposes carry equal cleartext handoff-risk classification, because the artifact each produces is equally readable once it leaves the vault.

## Steps

## Parallelization

The contract, operation-state, and serialization steps carry hard ordering: the typed purposes and requests must exist before the operation state can reference them, and both must exist before the locked serialization can compose them. The public re-export follows the service. The two proof steps run against the finished service. The CLI routing step depends on the service being the sole public orchestration API. The risk metadata and regenerated reference pages run last, from the frozen live surface.

This plan depends on stable profile and storage authorities, which are landed. It shares no files with the reset, evidence, or custody plans and may run in parallel with them.

## Verification

Crash-window suites pass: every prepared and replace crash window recovers honestly in a fresh process, with restrictive temporary permissions, parent-directory durability, same-target exclusion under concurrent export, and no premature completion event for an artifact that was not durably published.

Both purposes provably use the same service and the same bundle schema, and their categories are derived from serialized fields and registry-carried namespaces rather than a static CLI-owned list, while their distinct purpose metadata survives.

The CLI owns no direct serialization, target write, completion event, or static subject-access category list; the export service is the sole public orchestration API.

Both purposes carry equal cleartext handoff-risk classification, and the sealed recovery archive remains separate with its own semantics intact.

A fresh-context honesty review runs against this plan's closure summary before the plan is declared complete.
