---
tags:
  - '#plan'
  - '#desktop-service-installation'
date: '2026-10-09'
tier: L1
related:
  - '[[2026-10-09-desktop-service-installation-adr]]'
  - '[[2026-10-07-application-distribution-windows-versioned-msi-adr]]'
  - '[[2026-10-04-runtime-manager-architecture-supervisor-contract-adr]]'
modified: '2026-10-09'
body_schema: body-v2
body_hash: 'sha256:4a7cc6b5d80a3b68c3e37f92eaefdda279cd7a72675ee3f24280b96b2802f869'
---

# `desktop-service-installation` plan

## Description

Approved 2026-10-09

Authorization: the operator requests implementing an internal Tauri service installer for user or machine scope and future TUI/CLI runtime availability. The service-installation ADR governs kit delivery and bootstrap, existing MSI decisions govern transactional ownership/publication, and the supervisor contract governs runtime lifetime. Execute sequentially in this worktree and never register login startup on this development host.

## Steps

- [x] `S01` - Implement verified portable installation-kit admission, scoped native bootstrap, and authenticated owner-backed MSI installation admission.; `native/installer bootstrap and runner, native/application installation contract, package layout and installer CMake, dev/packaging native kit builder and Windows MSI authoring/database verification and tests, governing ADRs.`.
- [ ] `S02` - Integrate the scoped Tauri install command and missing-installation recovery with verification; `native desktop manager and tests, shell IPC and sign-in contracts and UI, native build snapshot, scoped checks and review`.

## Parallelization

Work executes sequentially in this worktree. No delegation is planned. Preserve unrelated changes and avoid native registration on this development host.

## Verification

Use real filesystem/serialization and native MSI admission boundaries. Check scoped kit assembly, refusal of wrong identity/artifact/scope, typed runner outcomes and manager dispatch after publication. Run owning Rust tests, formatting and clippy, Python scoped lint/type/tests and frontend type/lint checks. Record disposable-host installation/login acceptance as outstanding when the execution session lacks interactive desktop access.
