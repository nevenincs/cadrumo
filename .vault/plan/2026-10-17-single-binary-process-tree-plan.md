---
tags:
  - '#plan'
  - '#single-binary-process-tree'
date: '2026-10-17'
tier: L1
related:
  - '[[2026-10-17-single-binary-process-tree-adr]]'
  - '[[2026-10-04-runtime-manager-architecture-adr]]'
  - '[[2026-10-12-desktop-agent-host-adr]]'
  - '[[2026-10-03-application-packaging-interpreter-foundation-adr]]'
modified: '2026-10-17'
body_schema: body-v2
body_hash: 'sha256:fad21262bab49b4d2b0a6df76f741068f3ae3a4aecaa0cae36e36c0f4767791c'
---

# `single-binary-process-tree` plan

Run every Cadrumo-managed process from the one `cadrumo` binary so Windows groups them under the Cadrumo application.

## Description

Approved 2026-10-17. Basis: after the role model, the grouped view and the proof step were explained, the operator replied "single binary yes", then "commit and push. begin the work and execute. all approved".

Decision coverage: 2026-10-17-single-binary-process-tree-adr governs every Step and supersedes the package identity decision; its evidence is 2026-10-17-single-binary-process-tree-research. 2026-10-04-runtime-manager-architecture-adr, amended 2026-10-17, governs S04. 2026-10-12-desktop-agent-host-adr, amended 2026-10-17, governs S05. 2026-10-03-application-packaging-interpreter-foundation-adr governs the linked host in S01 to S03. S01 is the proof: when the operator reports no grouping, later Steps stop and the decision is reconsidered. The open Steps of 2026-10-16-windows-package-identity-plan are retired by S07. Package identity is removed by forward changes, never by reverting history.

## Steps

- [x] `S01` - Start the runtime from the desktop as the cadrumo binary in its runtime role through a linked interpreter host, and have the operator confirm the grouping; `native/desktop/src-tauri/src/main.rs`.
- [x] `S02` - Dispatch every declared role before window initialization, refuse unknown roles, select the linked host per role at run time instead of by compile-time defines, and start every desktop helper (runtime session commands, aeat sign-in and profile commands) as a role; `native/desktop/src-tauri/src/launch.rs`.
- [ ] `S03` - Bind desktop session holder admission to its role invocation and refuse holders the runtime started, then make sys.executable the cadrumo binary in its interpreter role so runtime workers and the KDF child re-enter the same binary; `native/interpreter/windows/host.c`.
- [ ] `S04` - Run the machine lifecycle broker and the manager as roles and identify broker, manager and runtime by image plus role for supervision, startup items, quiescence and termination, with tests, so no runtime host runs outside a Cadrumo tree; `native/manager/src/supervision/launch.rs`.
- [ ] `S05` - Run the agent service and agent as roles and bind service admission to image, role, module and invocation, with tests; `src/cadrumo_agent_service`.
- [ ] `S06` - Ship one cadrumo image for these roles in the package layout, build and assembly verification; `native/package-layout.json`.
- [ ] `S07` - Remove the package identity claims, the development registration command and its tests, and retire the package identity plan; `dev/packaging/native/package_identity.py`.
- [ ] `S08` - Dispatch the same roles on Linux and macOS; `native/interpreter/posix`.
- [ ] `S09` - Accept grouping, containment and admission on a disposable host; `native/installer`.

## Parallelization

S01 precedes every other Step. S02 and S03 follow S01 and touch disjoint files. S04 and S05 follow S02 and can run in parallel. S06 follows S03 to S05. S07 can run after S01 confirms the grouping. S08 follows S02 and S03. S09 is last. Builds that replace a running stage are coordinated with the session that owns the Debug build; no step registers anything on the operator's machine.

## Verification

- A command-line process list shows every Cadrumo-managed process running the one `cadrumo` image with its role argument, parented within one tree, and the operator confirms they appear under the Cadrumo application in Task Manager.
- An unknown role is refused before any window or interpreter starts; the desktop starts with no argument; existing CLI passthrough arguments are unchanged.
- Workers and the KDF child started through `sys.executable` run the same image in its interpreter role.
- Admission accepts each role only from its exact invocation and kernel peer evidence and refuses a peer that claims a role it was not started with, in isolated fixtures.
- Closing the desktop leaves no Cadrumo process behind; kill-on-close containment holds for every descendant.
- No image carries a package identity claim and no build, test or install registers a package.
