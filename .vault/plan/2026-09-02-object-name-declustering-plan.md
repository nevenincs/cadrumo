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
modified: '2026-09-02'
body_schema: body-v2
body_hash: 'sha256:0fcd9b38bb3302f3bef98e9561f76c9c24c8b7a4ead03d61ef492447f7dac564'
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

- [ ] `W01.P01.S01` - Emit complete declaration records with qualified locators, stable finding identifiers, source-byte hashes, and an inventory digest; `dev/audit/object_names.py`.
- [ ] `W01.P01.S02` - Cover deterministic identities, digest stability, and source drift reporting with focused regression tests; `dev/audit/tests/test_object_names.py`.

### Phase `W01.P02` - reviewed manifest authority

Define the typed reviewed intent that selects and constrains every proposed rename operation.

- [ ] `W01.P02.S03` - Implement the typed reviewed rename-manifest loader and reject ambiguous, incomplete, or stale intent; `dev/quality/object_name_manifest.py`.
- [ ] `W01.P02.S04` - Test manifest parsing, uniqueness constraints, stale preconditions, and fail-closed validation; `dev/quality/tests/test_object_name_manifest.py`.

### Phase `W01.P03` - evidence graph and scheduling

Derive deterministic operation-to-surface components and explainable risk ordering from existing analyzers.

- [ ] `W01.P03.S05` - Build deterministic hard-edge operation-to-file components and explainable risk ordering from installed analyzer signals; `dev/quality/object_name_graph.py`.
- [ ] `W01.P03.S06` - Test component isolation, shared-file coupling, stable ordering, and risk-evidence rendering; `dev/quality/tests/test_object_name_graph.py`.

## Wave `W02` - receipt-bound rehearsal and replay

Implement controlled transformations, disposable current-tree rehearsal, and identical fail-closed live replay on the Wave W01 contracts.

### Phase `W02.P04` - controlled transformation engine

Implement syntax-aware edits whose changed paths and bytes are bounded by the reviewed manifest.

- [ ] `W02.P04.S07` - Declare LibCST as a direct development dependency for controlled syntax-preserving Python edits; `pyproject.toml`.
- [ ] `W02.P04.S08` - Refresh the locked dependency graph after the direct LibCST declaration; `uv.lock`.
- [ ] `W02.P04.S09` - Implement bounded syntax-aware rename transformations with byte-precondition and allowlist enforcement; `dev/quality/object_name_transform.py`.
- [ ] `W02.P04.S10` - Test exact edits, unsupported constructs, changed-path bounds, and byte-level refusal behavior; `dev/quality/tests/test_object_name_transform.py`.

### Phase `W02.P05` - disposable rehearsal and receipt

Rehearse the exact plan against a disposable copy of the current dirty tree and emit an auditable receipt.

- [ ] `W02.P05.S11` - Implement disposable current-tree rehearsal and immutable receipt generation in the system temporary directory; `dev/quality/object_name_rehearsal.py`.
- [ ] `W02.P05.S12` - Test dirty and untracked input capture, isolated execution, receipt determinism, and source-tree immutability; `dev/quality/tests/test_object_name_rehearsal.py`.

### Phase `W02.P06` - live replay and postconditions

Replay only a matching receipt against live files and enforce fail-closed postconditions.

- [ ] `W02.P06.S13` - Implement receipt-bound live replay with preflight validation, atomic writes, and required postconditions; `dev/quality/object_name_replay.py`.
- [ ] `W02.P06.S14` - Test stale receipts, unexpected paths, failed gates, interrupted writes, and successful replay; `dev/quality/tests/test_object_name_replay.py`.

## Wave `W03` - operator CLI and pilot proof

Expose the safe workflow through the repository CLI surface and prove it on one low-risk leaf component without broadening scope.

### Phase `W03.P07` - operator CLI

Compose inventory, planning, rehearsal, replay, and verification behind one safe command contract.

- [ ] `W03.P07.S15` - Compose inventory, plan, rehearse, apply, and verify modes behind a fail-closed declustering CLI; `dev/quality/object_name_declustering.py`.
- [ ] `W03.P07.S16` - Test CLI argument contracts, structured output, default rehearsal, explicit apply, and exit semantics; `dev/quality/tests/test_object_name_declustering.py`.

### Phase `W03.P08` - Justfile fix target

Expose the declustering command as a discoverable mutation recipe whose default behavior is non-destructive.

- [ ] `W03.P08.S17` - Add the grouped fix-object-names recipe with pass-through arguments and rehearsal as its no-argument default; `Justfile`.
- [ ] `W03.P08.S18` - Test recipe discovery, command forwarding, safe defaults, and the absence of implicit live mutation; `dev/quality/tests/test_object_name_declustering_recipe.py`.

### Phase `W03.P09` - low-risk pilot rehearsal

Demonstrate the workflow on one reviewed leaf component and record evidence before any live rename.

- [ ] `W03.P09.S19` - Author one reviewed low-risk leaf-component manifest with exact finding and byte preconditions; `dev/quality/object_name_rename_manifest.toml`.
- [ ] `W03.P09.S20` - Run the Justfile rehearsal and record scope, receipt, gate results, residual findings, and unchanged-live-tree proof; `.vault/audit/2026-09-02-object-name-declustering-pilot-rehearsal-audit.md`.

## Parallelization

Waves are sequential: Wave W01 defines identities and dependency components consumed by Wave W02, and Wave W03 composes only the settled Wave W02 contracts. Within Wave W01, Phase P01 precedes P02 and P03; P02 and P03 may then proceed in parallel. Wave W02 is sequential from dependency declaration and transformation through rehearsal to replay. Wave W03 is sequential from CLI composition through the Justfile recipe to the pilot. Test steps may be developed with their owning implementation steps, but each phase lands as one coherent contract.

## Verification

Focused contract tests must pass for inventory, manifest, graph, transformation, rehearsal, replay, CLI, and recipe behavior.

Invoking just fix-object-names with no arguments must complete a disposable rehearsal while leaving tracked, dirty, and untracked live-tree content unchanged. Explicit apply must refuse missing or stale receipts, changed byte preconditions, unsupported edits, unexpected changed paths, and failed gates. Rehearsal and replay must report an actual changed-path set equal to the manifest allowlist and retain stable finding identities across reruns.

The pilot audit must record its temporary location, receipt digest, selected component, analyzer evidence, verification results, residual findings, and unchanged-live-tree proof. The object-name audit must report no newly introduced finding, and the pilot finding may be absent only after an explicitly approved live replay.

Repository import, architecture, generated-reference, type, lint, semantic-overlap, and clone gates must pass for affected surfaces. No compatibility shim, forwarding facade, fallback import, or duplicate authority may be introduced. Plan conformance, feature-scoped Vaultspec checks, and git diff whitespace validation must pass. Completion requires all twenty Steps to be closed; execution still requires explicit plan approval.
