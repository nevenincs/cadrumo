---
tags:
  - '#plan'
  - '#export-publication'
date: '2026-07-17'
modified: '2026-07-25'
tier: L1
related:
  - '[[2026-07-15-cli-authority-verb-conformance-adr]]'
  - '[[2026-07-15-cli-authority-verb-conformance-research]]'
  - '[[2026-07-15-cli-authority-verb-conformance-reference]]'
  - '[[2026-07-16-cli-authority-verb-conformance-duplication-authority-audit]]'
  - '[[2026-07-17-cli-authority-verb-conformance-audit]]'
  - '[[2026-07-15-cli-authority-verb-conformance-plan]]'
  - '[[2026-07-17-export-publication-audit]]'
  - '[[2026-07-17-export-publication-adr]]'
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
- [x] `S07` - Route both config profile export and subject-access-request through the sole portable-export application service and remove direct serialization, target writes, completion events, and static SAR category ownership from the CLI; `src/cadrumo/entrypoints/cli/_config/_profile_bundle.py`.
- [x] `S08` - Migrate the export family help, risk, and cleartext handoff-risk metadata to the accepted grammar with equal classification for both purposes; `src/cadrumo/application/operator_surface/_risk_table.py`.
- [x] `S09` - Regenerate the operator reference pages for portable export and subject access from the frozen live surface; `docs/reference/import-export-and-evidence.md`.
- [x] `S10` - Gated requirement surfaced by the export durable-layer review, latent until S07 wires both export doors through the shared service: make reconcile_prepared_exports hold the per-destination lock (or a repository lock spanning staged-temp removal and journal delete) per operation, or guarantee the S07 call site runs reconcile only at exclusive startup, so a reconcile concurrent with a live same-target export cannot unlink the live staged temp and spuriously fail os.replace, gated on a test that holds the destination lock and proves reconcile does not remove the live staged temp or raise a spurious ProfileExportError; `src/cadrumo/application/user_profile/_bundle_export.py, src/cadrumo/application/user_profile/tests/test_bundle_export_recovery.py`.
- [x] `S11` - Decide and implement whether a crash after os.replace succeeds but before the PROFILE_EXPORTED audit event eventually emits that event: adopt the three-phase journal (PREPARED, then replace plus fsync transitioning to COMPLETED, then emit the event, with reconcile completing a COMPLETED-but-eventless operation), closing the un-audited data-egress window and wiring the currently-dead COMPLETED operation-state enum, a data-egress audit-completeness posture item with limited privacy impact (a local file at the operator own path, not remote transmission), gated on no durably-published bundle lacking a PROFILE_EXPORTED event after reconcile; `src/cadrumo/application/user_profile/_bundle_export.py, src/cadrumo/application/user_profile/tests/test_bundle_export_recovery.py`.
- [x] `S12` - Wire the built crash-recovery reconciliation into the production publication path so a crashed export's orphan operation journal and its cleartext staged temporary file are cleared by an operator-reachable code path rather than only by the test harness, choosing the trigger from how the journal and staged temp are actually keyed; `src/cadrumo/application/user_profile/_bundle_export.py, src/cadrumo/application/user_profile/tests/test_bundle_export_recovery.py`.
- [x] `S13` - Make the personal-data category derivation exhaustive by construction so a new portable-bundle schema field cannot silently vanish from the subject-access disclosure, classifying every bundle field as category-mapped, envelope metadata, or carried-namespace derived and refusing an unclassified field, gated on a non-tautological test that enumerates the model's own fields and proves an unmapped field fails; `src/cadrumo/application/user_profile/_bundle_export_contracts.py, src/cadrumo/application/user_profile/tests/test_bundle_export.py`.
- [x] `S14` - Isolate each operation inside the export reconciliation sweep so one unreadable or unfinalisable journal cannot starve every later-ordered operation, returning a typed reconciliation that reports the isolated failures rather than swallowing them, gated on a poisoned-journal test proving a healthy operation still reconciles alongside a failing one; `src/cadrumo/application/user_profile/_bundle_export.py, src/cadrumo/application/user_profile/_bundle_export_operation.py, src/cadrumo/application/user_profile/tests/test_bundle_export_recovery.py`.
- [x] `S15` - Expose an operator-invocable export reconciliation verb under the app root so a crashed operator who never exports again can still clear the orphan journal and its cleartext staged temporary file, reporting cleared and failed operations through the typed notice channel, gated on a crash-simulating test driven through the CLI runner; `src/cadrumo/entrypoints/cli/_app_maintenance.py, src/cadrumo/entrypoints/cli/_app_maintenance_payloads.py, src/cadrumo/entrypoints/cli/tests/test_app_maintenance_export_reconcile.py`.
- [x] `S16` - Close the pre-journal crash window so no cleartext bundle can exist on disk without a journal entry naming it, recording the durable operation before staging rather than after, and extending orphan removal to the hardened writer's own inner temporary file whose name the current suffix guard rejects, gated on a hard-killed child crashing inside the widened window with no cleartext surviving; `src/cadrumo/application/user_profile/_bundle_export.py, src/cadrumo/application/user_profile/tests/test_bundle_export_recovery.py`.
- [x] `S17` - Make the subject-access completeness claim true by deriving the excluded personal-data categories from the bundle coverage manifest, carrying them beside the included categories through the operation journal and the operator payload, and rewriting the catalogue notice to state both what the archive holds and what it omits, gated on a test asserting the excluded set matches the manifest; `src/cadrumo/application/user_profile/_bundle_export_contracts.py, src/cadrumo/application/user_profile/_bundle_export_operation.py, src/cadrumo/entrypoints/cli/_config/_profile_bundle.py`.
- [x] `S18` - Surface the reconciliation failures the pre-flight sweep discards so the export path an operator actually takes reports a leftover journal that may still describe cleartext bytes, carrying them on the export result and emitting them as a warning notice, gated on a test proving the export envelope warns when a journal cannot be reconciled; `src/cadrumo/application/user_profile/_bundle_export.py, src/cadrumo/entrypoints/cli/_config/_profile_bundle.py`.
- [x] `S19` - Classify a journal that vanished mid-scan as a skip rather than a failure so a peer process completing normally cannot make the sweep tell an operator that an unencrypted file may remain, gated on a test removing a journal between scan and reconcile; `src/cadrumo/application/user_profile/_bundle_export_operation.py, src/cadrumo/application/user_profile/tests/test_bundle_export_recovery.py`.
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
