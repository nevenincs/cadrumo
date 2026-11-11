---
tags:
  - '#plan'
  - '#native-modularity'
date: '2026-11-02'
tier: L1
modified: '2026-11-02'
body_schema: body-v2
body_hash: 'sha256:a27d330ba548d0fd5ae7794b9b8342f38ab70dcec7e0bc7015039d0c4b3c068a'
related:
  - '[[2026-10-04-canonical-environment-adr]]'
  - '[[2026-10-04-desktop-shell-adr]]'
---














# `native-modularity` plan



## Description

Approved 2026-11-02

The user explicitly authorized repository-wide TS/TSX and Rust modularization, canonical settings and multi-language health checks. Preserve behavior, existing working changes, admission and storage authority. Existing canonical-environment and desktop/runtime decisions govern; no replacement authority is proposed. Size is an inventory heuristic, never a line-count gate. Generated code and data are assessed separately.




## Steps

- [ ] `S01` - Inventory all authored frontend and Rust modules and record bounded refactor assignments with governing decisions; `native, dev/quality, justfile`.
- [ ] `S02` - Integrate multi-language code health and existing frontend and Rust verification gates; `dev/quality, dev/audit, justfile, native/desktop/frontend`.
- [ ] `S03` - Refactor frontend monoliths and consolidate reusable logic and configurable presentation settings; `native/desktop/frontend/src`.
- [ ] `S04` - Refactor native Rust monoliths and consolidate shared configuration through the canonical environment contract; `native/application, native/platform, native/manager, native/desktop/src-tauri`.
- [ ] `S05` - Verify the complete authored-module census, duplication findings, behavior and integrated quality gates; `native, dev, justfile`.













## Parallelization

S02 health tooling may run concurrently with S03 frontend and S04 Rust source refactoring under disjoint ownership. Supervisor owns shared metadata, justfile integration, final checks and commits. Terra xhigh handles discovery and bounded transformations; Sol medium handles sensitive module extractions. Supervisor owns cross-language configuration architecture. S05 follows all implementation.




Current delegated lanes (user-directed autonomous execution):
- S04/S05 Sol medium native lane: native application view-stream failure, desktop Rust gate failures, then sede_view decomposition. Own Rust verification for this batch, no frontend or Python changes.
- S03 Sol medium frontend lane: ledger orchestration and read-session modules, excluding App.tsx, Modelo and AEAT surfaces under concurrent work. Own focused frontend tests.
- S01/S02/S05 Terra xhigh tooling lane: health tooling and justfile integration, reproducible authored-module census and completed/remaining assessment. Own Python tooling tests, no product source changes.
The parent owns App.tsx and its new shell-only modules, settings architecture, shared metadata and final integrated review. Consumer edits stay inside assigned areas; cross-lane needs are reported. Workers complete their own commands and report results independently; parent does not poll or wait on their internal commands. Preserve concurrent user work. Shared full frontend checks wait until sources stabilize, coordinated by messages without command polling.

## Verification

Run focused regression tests and existing frontend npm check, CMake-owned Rust tests/quality, and Python gates appropriate to tooling changes. Exercise scanner defects using isolated fixtures. Audit all authored modules for cohesion and duplication, documenting justified generated/data exclusions. Final integrated review is required; unresolved verification leaves Steps open.




