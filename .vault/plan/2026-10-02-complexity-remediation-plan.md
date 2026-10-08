---
tags:
  - '#plan'
  - '#complexity-remediation'
date: '2026-10-02'
tier: L1
related:
  - '[[2026-07-01-import-centralization-adr]]'
  - '[[2026-09-11-justfile-design-adr]]'
  - '[[2026-08-11-tui-architecture-adr]]'
  - '[[2026-09-04-tui-architecture-authenticated-tui-visibility-adr]]'
modified: '2026-10-02'
body_schema: body-v2
body_hash: 'sha256:daf4c0775385c75328eb1adbb8e48b0d47e5c57f8808112b0c98e72b86243fa3'
---

# `complexity-remediation` plan

## Description

Approved 2026-10-02

The operator requested running `just audit-complexity` and reducing all production findings to zero. Authorization covers behavior-preserving refactoring and prerequisite parser repairs, using the existing detector thresholds and source population. Preserve pre-existing edits and calculation, persistence, public interface and security semantics. Do not commit or stage without an operator request.

The accepted import-centralization decision governs canonical defining modules and dependency direction throughout. The accepted justfile-design decision governs the advisory command and its exit contract. Local helper extraction within those commitments requires no new costly decision. S01 preserves existing operation-envelope and authenticated visibility contracts while reconciling declaration parsing. S03 may update exact imports and symbol references in outside consumers when operations contracts move atomically; broader behavior changes there are outside its assignment.

## Steps

- [x] `S01` - Restore parseable TUI declaration sources while preserving reconciled behavior; `src/cadrumo/entrypoints/tui/declarations`.
- [x] `S02` - Decompose development registry delta migration hotspots without changing candidate semantics; `dev/registry/edition_delta_migration.py dev/registry/edition_family_delta.py dev/registry/tests`.
- [x] `S03` - Decompose product operation lifecycle and public contract hotspots without changing security behavior; `src/cadrumo/application/operations`.
- [x] `S04` - Decompose development packaging hotspots while preserving artifact, installer, and evidence contracts; `dev/packaging packaging`.
- [ ] `S05` - Verify the complete live complexity inventory and review the integrated refactors; `dev/audit/complexity.py .vault/audit`.
- [ ] `S06` - Decompose product application hotspots in bounded disjoint groups while preserving behavior; `src/cadrumo/application`.
- [ ] `S07` - Decompose entrypoint hotspots while preserving command and TUI contracts; `src/cadrumo/entrypoints`.
- [x] `S08` - Decompose domain core and harness hotspots while preserving typed authority and resource contracts; `src/cadrumo/domain src/cadrumo/core src/cadrumo_harness`.
- [ ] `S09` - Decompose remaining development registry quality and locale hotspots within existing authorities; `dev/registry dev/quality dev/locales dev/audit dev/test_runs dev/docs dev/corpus dev/env dev/ci`.
- [x] `S10` - Decompose installed acceptance harness hotspots while preserving their observable contracts; `dev/acceptance`.
- [ ] `S11` - Decompose adapter hotspots while preserving persistence, local-runtime, and outbound integration contracts; `src/cadrumo/adapters`.

## Parallelization

Independent Steps may run concurrently with explicit disjoint file ownership assigned by the supervisor. S01 owns declarations and required work-create integration. S02 owns registry delta migration and family-delta modules plus atomic consumers. S03 owns application operations plus necessary consumer import changes. The supervisor currently owns packaging generator and constraint parser work under S04. Further bounded assignments under S06-S09 follow the live inventory. Coordinate overlapping consumer files before editing. The supervisor alone writes shared plan and ledger records and runs full-tree complexity, integrated type/import checks and final review. Workers run independent focused checks and report paths and exit statuses. Do not commit or stage without an operator request.

## Verification

`just audit-complexity` must complete with exit 0 and report zero current hotspots over every configured production root. Detector semantics and coverage remain unchanged. Each refactored surface passes relevant existing tests, formatting, lint and focused type checks. Classify pre-existing unrelated failures separately and review integrated behavior. Steps close only on applicable verification evidence; plan completion requires the final review.
