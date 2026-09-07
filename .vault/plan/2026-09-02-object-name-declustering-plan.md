---
tags:
  - '#plan'
  - '#object-name-declustering'
date: '2026-09-02'
tier: L3
related:
  - '[[2026-09-02-object-name-declustering-adr]]'
  - '[[2026-09-02-object-name-declustering-research]]'
  - '[[2026-09-02-object-name-declustering-reference]]'
modified: '2026-09-07'
body_schema: body-v2
body_hash: 'sha256:cfdb5349cb6653a01079f3dc89eb43ad2bde392138d3d1fe069183abab1b515f'
---

<!-- RETIRED: S21, S22 -->

# `object-name-declustering` plan

## Description

This L3 plan executes the accepted object-name declustering ADR using the audit findings, implementation research, and repository reference already linked in frontmatter. It separates stable finding identity from byte preconditions, groups operations by hard operation-to-file dependencies, and permits live changes only when an unchanged rehearsal receipt is explicitly replayed.

The operator surface is just fix-object-names. With no arguments it inventories, plans, and rehearses in the system temporary directory without modifying the live tree. Live application requires an explicit apply mode and a matching receipt; stale bytes, unexpected paths, unsupported syntax, or failed verification cause refusal. This plan builds the safety mechanism and records a pilot rehearsal. It does not authorize bulk semantic consolidation or an unreviewed rename sweep.

## Steps

## Wave `W01` - deterministic inventory and component authority

Establish the canonical inventory, reviewed manifest, and hard dependency components that every later mutation consumes.

### Phase `W01.P01` - canonical inventory identity

Extend the existing object-name authority with complete stable machine identity and drift guards.

- [x] `W01.P01.S01` - Emit complete declaration records with qualified locators, stable finding identifiers, source-byte hashes, and an inventory digest; `dev/audit/object_names.py`.
- [x] `W01.P01.S02` - Cover deterministic identities, digest stability, and source drift reporting with focused regression tests; `dev/audit/tests/test_object_names.py`.

### Phase `W01.P02` - reviewed manifest authority

Define the typed reviewed intent that selects and constrains every proposed rename operation.

- [x] `W01.P02.S03` - Implement the typed reviewed rename-manifest loader and reject ambiguous, incomplete, or stale intent; `dev/quality/object_name_manifest.py`.
- [x] `W01.P02.S04` - Test manifest parsing, uniqueness constraints, stale preconditions, and fail-closed validation; `dev/quality/tests/test_object_name_manifest.py`.

### Phase `W01.P03` - evidence graph and scheduling

Derive deterministic operation-to-surface components and explainable risk ordering from existing analyzers.

- [x] `W01.P03.S05` - Build deterministic hard-edge operation-to-file components and explainable risk ordering from installed analyzer signals; `dev/quality/object_name_graph.py`.
- [x] `W01.P03.S06` - Test component isolation, shared-file coupling, stable ordering, and risk-evidence rendering; `dev/quality/tests/test_object_name_graph.py`.

## Wave `W02` - receipt-bound rehearsal and replay

Implement controlled transformations, disposable current-tree rehearsal, and identical fail-closed live replay on the Wave W01 contracts.

### Phase `W02.P04` - controlled transformation engine

Implement syntax-aware edits whose changed paths and bytes are bounded by the reviewed manifest.

- [x] `W02.P04.S07` - Declare LibCST as a direct development dependency for controlled syntax-preserving Python edits; `pyproject.toml`.
- [x] `W02.P04.S08` - Refresh the locked dependency graph after the direct LibCST declaration; `uv.lock`.
- [x] `W02.P04.S09` - Implement bounded syntax-aware rename transformations with byte-precondition and allowlist enforcement; `dev/quality/object_name_transform.py`.
- [x] `W02.P04.S10` - Test exact edits, unsupported constructs, changed-path bounds, and byte-level refusal behavior; `dev/quality/tests/test_object_name_transform.py`.

### Phase `W02.P05` - disposable rehearsal and receipt

Rehearse the exact plan against a disposable copy of the current dirty tree and emit an auditable receipt.

- [x] `W02.P05.S11` - Implement disposable current-tree rehearsal and immutable receipt generation in the system temporary directory; `dev/quality/object_name_rehearsal.py`.
- [x] `W02.P05.S12` - Test dirty and untracked input capture, isolated execution, receipt determinism, and source-tree immutability; `dev/quality/tests/test_object_name_rehearsal.py`.

### Phase `W02.P06` - live replay and postconditions

Replay only a matching receipt against live files and enforce fail-closed postconditions.

- [x] `W02.P06.S13` - Implement receipt-bound live replay with preflight validation, atomic writes, and required postconditions; `dev/quality/object_name_replay.py`.
- [x] `W02.P06.S14` - Test stale receipts, unexpected paths, failed gates, interrupted writes, and successful replay; `dev/quality/tests/test_object_name_replay.py`.

## Wave `W03` - operator CLI and pilot proof

Expose the safe workflow through the repository CLI surface and prove it on one low-risk leaf component without broadening scope.

### Phase `W03.P07` - operator CLI

Compose inventory, planning, rehearsal, replay, and verification behind one safe command contract.

- [x] `W03.P07.S15` - Compose inventory, plan, rehearse, apply, and verify modes behind a fail-closed declustering CLI; `dev/quality/object_name_declustering.py`.
- [x] `W03.P07.S16` - Test CLI argument contracts, structured output, default rehearsal, explicit apply, and exit semantics; `dev/quality/tests/test_object_name_declustering.py`.

### Phase `W03.P08` - Justfile fix target

Expose the declustering command as a discoverable mutation recipe whose default behavior is non-destructive.

- [x] `W03.P08.S17` - Add the grouped fix-object-names recipe with pass-through arguments and rehearsal as its no-argument default; `Justfile`.
- [x] `W03.P08.S18` - Test recipe discovery, command forwarding, safe defaults, and the absence of implicit live mutation; `dev/quality/tests/test_object_name_declustering_recipe.py`.

### Phase `W03.P09` - low-risk pilot rehearsal

Demonstrate the workflow on one reviewed leaf component and record evidence before any live rename.

- [x] `W03.P09.S23` - Bind manifest staleness to selected identities and declared bytes so unrelated concurrent inventory churn cannot invalidate a leaf operation; `dev/quality/object_name_manifest.py, dev/quality/tests/test_object_name_manifest.py`.
- [x] `W03.P09.S24` - Bind rehearsal receipts and replay drift checks to the reviewed component while preserving unrelated concurrent bytes; `dev/quality/object_name_rehearsal.py, dev/quality/object_name_replay.py, dev/quality/tests/test_object_name_rehearsal.py, dev/quality/tests/test_object_name_replay.py`.
- [x] `W03.P09.S19` - Author one reviewed low-risk leaf-component manifest with exact finding and byte preconditions; `dev/quality/object_name_rename_manifest.toml`.
- [x] `W03.P09.S25` - Build the sole rehearsal component exactly once from the hash-verified disposable snapshot; `dev/quality/object_name_rehearsal.py, dev/quality/object_name_declustering.py, dev/quality/tests/test_object_name_rehearsal.py, dev/quality/tests/test_object_name_declustering.py`.
- [x] `W03.P09.S20` - Run the Justfile rehearsal and record scope, receipt, gate results, residual findings, and unchanged-live-tree proof; `.vault/audit/2026-09-02-object-name-declustering-pilot-rehearsal-audit.md`.
- [x] `W03.P09.S26` - Apply the reviewed pilot receipt and verify the live finding reduction without compatibility residue; `dev/registry/generate_result_disposition_fragments.py, dev/registry/result_disposition_fragment_generator.py`.

## Wave `W04` - receipt scope and teardown authority

Reopen the S23 objective. The accepted ADR requires that finding identity survive unrelated movement while execution refuses concurrent byte changes, and the S23 review recorded at high severity that the objective was not achieved downstream of the validator. S24 was its closure step and its churn test perturbs a file outside the Python declaration census, so it cannot fail -- a high finding reported closed on a gate that is green because it cannot fail. Twenty-one refusals of one four-operation batch, none attributable to the renames, are the live evidence. This Wave carries the distinction through receipt generation and replay with a test that can fail, states the teardown invariant a cleanup path violated by reverting an apply whose gates all passed, and gives the retained transaction root a disposition path.

### Phase `W04.P10` - receipt scope carried through replay

Rehearsal records the current scanned inventory digest, replay compares it against a freshly scanned current inventory, and the authored inventory value stays bound only through the exact manifest digest. The remedy is the one the S23 review already wrote; what is missing is that it never reached receipt generation and replay, and that the test which should have caught it perturbs a non-Python file.

- [x] `W04.P10.S27` - Carry the S23 distinction through rehearsal: require the copied inventory to equal the supplied current inventory, record that current digest in the receipt, and leave the authored inventory value bound only through the exact manifest digest, since the receipt currently records the manifest value and refuses at the next mandatory phase whatever the validator tolerated (Terra xhigh fixes and refactors); `dev/quality/object_name_rehearsal.py, dev/quality/object_name_replay.py`.
- [x] `W04.P10.S28` - Require replay to compare the receipt inventory against a freshly scanned current inventory and the exact manifest digest, without also equating current inventory to the authored value, so unrelated declaration churn no longer invalidates a leaf operation whose own bytes and graph evidence are unchanged (Terra xhigh fixes and refactors); `dev/quality/object_name_replay.py`.
- [x] `W04.P10.S29` - Replace the vacuous churn test with one that can fail: perturb a real Python declaration so the current inventory digest actually moves, drive it through component derivation, rehearsal, receipt generation and replay preflight, and prove the case fails when receipt/current global-inventory equality is reintroduced, closing the end-to-end-churn-teeth gap S23 opened and S24 left standing (Luna max audit and mechanical); `dev/quality/tests/`.
- [x] `W04.P10.S30` - Measure the surviving validity window against live conditions, recording inventory-affecting commit rate, dirty-file count and cycle wall clock, and state plainly whether a rehearse-and-apply cycle can complete under concurrent development or whether the campaign requires an exclusive worktree (Luna max audit); `.vault/audit/`.

### Phase `W04.P11` - teardown authority and transaction disposition

State and enforce the invariant a cleanup path violated: removal of an artefact outside the unit of work is best-effort and may never convert a verified result into a failure, while removal whose success is semantically meaningful stays strict and says so. Then give the deliberately retained transaction root a recorded disposition, so `explicit operator inspection` resolves to an action rather than an accumulating directory.

- [ ] `W04.P11.S31` - State the teardown invariant in the accepted record and enforce it at both verified-copy removal sites, distinguishing an artefact that is evidence from one that is litter, since a WinError 145 raised from a finally converted an apply whose six gates had all passed into a rolled-back failure (Sol architecture); `.vault/adr/, dev/quality/object_name_replay.py`.
- [ ] `W04.P11.S32` - Give the retained transaction root a disposition path that verifies inertness before removal -- absent-paths empty and every backup byte-identical to both the live tree and the receipt baseline -- so operator inspection resolves to a recorded action, and dispose of the two roots outstanding from 2026-09-05 and 2026-09-06 (Terra xhigh fixes and refactors); `dev/quality/`.

## Parallelization

Waves are sequential: Wave W01 defines identities and dependency components consumed by Wave W02, and Wave W03 composes only the settled Wave W02 contracts. Within Wave W01, Phase P01 precedes P02 and P03; P02 and P03 may then proceed in parallel. Wave W02 is sequential from dependency declaration and transformation through rehearsal to replay. Wave W03 is sequential from CLI composition through the Justfile recipe to the pilot. Test steps may be developed with their owning implementation steps, but each phase lands as one coherent contract.

## Verification

Focused contract tests must pass for inventory, manifest, graph, transformation, rehearsal, replay, CLI, and recipe behavior.

Invoking just fix-object-names with no arguments must complete a disposable rehearsal while leaving tracked, dirty, and untracked live-tree content unchanged. Explicit apply must refuse missing or stale receipts, changed byte preconditions, unsupported edits, unexpected changed paths, and failed gates. Rehearsal and replay must report an actual changed-path set equal to the manifest allowlist and retain stable finding identities across reruns.

The pilot audit must record its temporary location, receipt digest, selected component, analyzer evidence, verification results, residual findings, and unchanged-live-tree proof. The object-name audit must report no newly introduced finding, and the pilot finding may be absent only after an explicitly approved live replay.

Repository import, architecture, generated-reference, type, lint, semantic-overlap, and clone gates must pass for affected surfaces. No compatibility shim, forwarding facade, fallback import, or duplicate authority may be introduced. Plan conformance, feature-scoped Vaultspec checks, and git diff whitespace validation must pass. Completion requires all twenty Steps to be closed; execution still requires explicit plan approval.
