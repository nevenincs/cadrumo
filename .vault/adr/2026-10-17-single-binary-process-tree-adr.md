---
tags:
  - "#adr"
  - "#single-binary-process-tree"
date: '2026-10-17'
related:
  - "[[2026-10-17-single-binary-process-tree-research]]"
  - "[[2026-10-16-application-distribution-windows-package-identity-adr]]"
  - "[[2026-10-04-runtime-manager-architecture-adr]]"
  - "[[2026-10-12-desktop-agent-host-adr]]"
  - "[[2026-10-03-application-packaging-interpreter-foundation-adr]]"
supersedes:
  - '2026-10-16-application-distribution-windows-package-identity-adr'
modified: '2026-10-17'
body_schema: 'body-v2'
body_hash: 'sha256:90a8362b11aa150ea0748655d67dc6029a300d5a66b6ac8890068540e5cd20b7'
---
# `single-binary-process-tree` adr: `One Cadrumo binary runs every Cadrumo process` | (**status:** `accepted`)

## Problem Statement

The operator requires every Cadrumo process to appear under the one Cadrumo application, with the `cadrumo` binary managing all of them. Task Manager splits the tree at every image boundary: the desktop, runtime, agent service, agent and bundled interpreter are separate executables, so each shows as its own row. Package identity, accepted in `2026-10-16-application-distribution-windows-package-identity-adr` to unify them, did not group them and weakened worker containment.

## Considerations

- `2026-10-17-single-binary-process-tree-research` records the evidence: same-image parent and child pairs nest in Task Manager while cross-image pairs split; every Debug process carried the Cadrumo package identity without grouping; unpackaged descendants of packaged processes escaped kill-on-close jobs; Chromium and Electron run every process from one executable with a role switch.
- `2026-10-04-runtime-manager-architecture-adr` names a separate `cadrumo-manager` image and identifies manager and runtime by image for startup, quiescence and termination.
- `2026-10-12-desktop-agent-host-adr` binds service admission to the packaged service image, module and invocation plus kernel peer evidence.
- `2026-10-03-application-packaging-interpreter-foundation-adr` owns the C interpreter host: restricted DLL search, the bundled CPython DLL and bridge, and launch profiles.

## Considered options

- **Package identity with external location:** did not group the processes and let unpackaged descendants escape kill-on-close jobs; rejected.
- **Keeping separate executables:** Task Manager splits at every image boundary; rejected.
- **One process for everything:** loses the runtime's crash isolation and worker containment; rejected.
- **One binary with role dispatch, every role its own process:** selected.

## Constraints

Accepted 2026-10-17: after the explanation of the role model, the grouped view and the proof step, the operator replied "single binary yes", then "commit and push. begin the work and execute. all approved".

1. **One binary.** Every Cadrumo-owned process runs the `cadrumo` executable: the desktop window, the machine lifecycle broker service, the manager, the runtime, the agent service, the agent, runtime workers, the KDF child and every helper the desktop starts. The separate runtime, agent-service, agent, manager and interpreter executables are no longer distributed for these roles.
2. **Role dispatch.** A reserved first argument selects the role. `main` dispatches it before any window, webview or Tauri initialization; no argument means the desktop. Unknown roles are refused.
3. **Python roles reuse the existing host.** The C interpreter host logic is linked into the binary and selected at run time instead of by compile-time defines. Restricted DLL search, the bundled CPython DLL and bridge, launch profiles and isolated initialization are unchanged. `sys.executable` is the `cadrumo` binary in its interpreter role, so a worker or KDF child started through `sys.executable` runs the same binary.
4. **Admission distinguishes roles by invocation.** Native admission keeps the digest-verified packaged image, now one image, and binds the role argument, module and exact invocation plus kernel peer evidence. A claimed role grants nothing; a peer is proven by how it was started.
5. **Containment is unchanged.** Owned processes stay in kill-on-close job objects with the existing launch methods; no package identity and no desktop-app breakaway policy.
6. **Package identity is retired.** This supersedes `2026-10-16-application-distribution-windows-package-identity-adr`. The identity claims in application manifests, the developer registration command and the planned installer registration are removed by forward changes through the implementing plan.
7. **External programs stay external.** WebView2, browsers started for authenticated reads and local model runtimes are not Cadrumo binaries and appear under their own application.
8. **The runtime is always part of Cadrumo.** The runtime host has exactly two legitimate parents, both the `cadrumo` binary: a manager role (started by the machine lifecycle broker service or by login startup) or the supervision core embedded in a running desktop. No path starts an unsupervised runtime host, so a runtime outside a Cadrumo tree is a defect. Every process the desktop starts, including the runtime session commands it uses to observe and hold sign-in and the `aeat` commands behind sign-in and profiles, runs as a role of the binary. Only programs the operator or an MCP client starts directly, `aeat`, `cadrumo-mcp` and the `cadrumo-runtime` administration commands, remain separate console entry points; they are clients of the runtime, not the runtime.
9. **Proof before migration.** The first implementing step makes the binary start one role of itself; the operator confirms the grouping before the remaining roles move.

## Implementation

We will run every Cadrumo-managed process from the one `cadrumo` binary, selected by a role argument. The L1 plan `2026-10-17-single-binary-process-tree-plan` sequences the proof, role dispatch with the linked host, per-role migration with admission and tests, interpreter re-entry, package layout and build, removal of package identity, and acceptance on a disposable host. Role names, the argument spelling and the order in which roles move are implementation details within these constraints.

## Rationale

Same-image nesting is the one grouping mechanism the evidence shows working on this machine, and it is the mechanism Chromium and Electron rely on. It keeps every existing process boundary, so crash isolation and containment are preserved, and it needs no registration, signing prerequisite or package state.

## Consequences

- Startup items, process quiescence, termination targeting and diagnostics identify Cadrumo processes by image plus role argument. `2026-10-04-runtime-manager-architecture-adr` and `2026-10-12-desktop-agent-host-adr` carry amendments for this.
- A manager started at sign-in or by the lifecycle broker is not a child of the desktop window, so its tree, runtime included, appears as its own Cadrumo background row; a desktop-hosted manager core nests its runtime under the window.
- Amended 2026-10-17 at the operator's direction that the runtime is either a service or part of the Cadrumo app and is never an orphan: the broker joins the roles, and helpers the desktop starts are roles rather than separate console entry points.
- Inside the group every line runs the same image and shows the same name; the role is visible in the process command line.
- The packaged executable count falls; manifests, version resources and signing cover one image for these roles.
- Linux and macOS use the same role dispatch.
- If the proof step shows no grouping, the remaining steps stop and this decision is reconsidered.

## Provider browser hook refinement 2026-10-17

Accepted within the owner's continued authorization to repair GUI provider sign-in. Installed Claude Code 2.1.302 supplies its browser override with exactly one URL argument and does not support an executable plus role arguments. A bounded browser handoff therefore reuses the same Cadrumo executable with one HTTPS URL argument. This is the sole exception to constraint 2's role-prefix shape: URL invocations are claimed before diagnostics, console attachment, webview or normal desktop dispatch, and fail closed without the login attempt's transient loopback port and correlation nonce. They never start a desktop, open a browser, read credentials or log the URL. The single image and existing containment are preserved.

The short-lived bridge sends the bounded URL to the helper that owns the attempt. The agent validates provider origin and correlation, emits its existing browser_action event, and acknowledges; the normal host opens the browser. Listener and bridge have bounded lifetimes, no durable signalling files, and no service registration. The provider still owns OAuth callback, token exchange and persistence. A new packaged helper image and direct provider-owned browser launching were rejected because they would respectively split the image tree or bypass the host-owned browser action. This records implementation scope, not completed authentication evidence.

## Amendment 2026-10-24: the components role

Basis: the owner's approval of 2026-10-24, "all approved, implemnet", answering the presented `2026-10-24-rust-component-provisioning-adr` and its two plans.

The roles gain `components` (`--role components`), which runs the Rust component engine of `2026-10-24-rust-component-provisioning-adr`. It is the first role that hosts no interpreter. Constraint 7 is unchanged: the Ollama program the engine installs from a pinned archive stays an external program, not a Cadrumo binary.
