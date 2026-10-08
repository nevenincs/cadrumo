---
tags:
  - '#adr'
  - '#runtime-manager-architecture'
date: '2026-10-08'
modified: '2026-10-08'
body_schema: 'body-v2'
body_hash: 'sha256:b900e2f9f2ef3a041c266bd670ca43f27bedc9ca37d8915bb68981863f228641'
related:
  - "[[2026-10-04-runtime-manager-architecture-adr]]"
  - "[[2026-10-08-runtime-manager-architecture-linux-placement-research]]"
  - "[[2026-10-04-runtime-manager-architecture-supervisor-contract-adr]]"
  - '[[2026-10-03-runtime-without-service-manager-adr]]'
  - '[[2026-09-26-mcp-purpose-authentication-adr]]'
---

# `runtime-manager-architecture` adr: `Proposed Linux placement amendment preserving native session admission` | (**status:** `proposed`)

## Problem Statement

The accepted manager architecture specifies user-systemd scope placement with a pipe fallback. Current native admission derives logind session identity from the supervised process's own cgroup. `2026-10-08-runtime-manager-architecture-linux-placement-research` shows why moving beneath the user manager can remove that identity. This proposal refines Linux placement only; it does not amend accepted text or authorize release activation.

## Considerations

- The operator authorized source implementation and builds except signing certificates. That authorizes preparing and reviewing this proposal; no weakened native session authority is inferred.
- Native process, owner, image, privilege and desktop-session checks remain binding in the manager and runtime.
- The current host has no qualifying graphical logind session; the available probe refuses it before launching children.
- Separate cgroup isolation is useful, but cannot substitute for native login identity or prove that a manager crash preserves the runtime.

## Considered options

- Retain mandatory `systemd-run --user` placement: no ruling changes, but Linux stays gated because upstream cgroup identity conflicts with current admission and there is no successful runner evidence.
- Direct child in the manager's verified native login session: proposed. It keeps existing admission and held-process supervision; it gives up mandatory separate cgroup placement and requires an autostart profile that does not kill the runtime when the manager exits.
- New authenticated login binding independent of the runtime's cgroup: deferred. This may support user-manager units but needs a coordinated authority design across admission, boot records, IPC, adoption and logout invalidation.

## Constraints

The manager and runtime must independently satisfy native same-owner, same-desktop-session admission. No environment session ID, guessed scope name, missing-session exception or remote session is admitted. Held pidfds and image/start-identity checks remain required. Runtime lifetime must remain independent of frontend and manager crashes. Root, elevated capability and unsupported native identity states still refuse.

Direct launch is eligible only on an installed autostart profile proven to place the manager in an admitted native session and to leave its runtime alive after manager failure. Failure to prove either property leaves that profile unavailable. Source authoring and a successful build do not establish eligibility.

## Implementation

We propose permitting the Linux manager to launch the runtime directly as an inherited-session child, with a separate process group and stop delivery through the held runtime pidfd. The manager holds its existing private supervisor channel and start claim. Systemd placement is not selected merely because a harmless process can enter a scope; any future placement must also retain the complete native identity and lifetime guarantees.

If approved, amend `2026-10-04-runtime-manager-architecture-adr` in these exact places:

- Replace the Linux Platform placement sentence beginning "The runtime is placed in its own cgroup" with: "Linux launches the runtime as a direct child in the manager's independently verified native desktop login session, with a separate process group and held-pidfd stop delivery. A systemd placement is eligible only after native runner evidence proves it preserves the same session identity and lifetime guarantees; entering a scope alone is insufficient. Unsupported autostart profiles refuse visibly."
- Append to the Placement and adoption constraint beginning "The runtime is never a descendant of a frontend": "On Linux an OS-owned native login-session cgroup is permitted; frontend-owned or manager-owned units that terminate the runtime when their owner exits are not. A separate runtime cgroup is not mandatory when preserving native session identity requires inherited-session placement."
- Replace the Linux Session end hypothesis with: "The manager observes its own native session ending and native shutdown, suppresses restarts, and sends session-end within the existing drain bound. Installed-runner evidence must cover logout, cancelled shutdown and manager failure; an autostart unit's SIGTERM behavior alone does not establish those guarantees."

The remaining lifecycle, identity, package versioning and acceptance constraints stay in force. This proposal does not choose a libsystemd minimum or a PID compatibility adapter. The proposal is retired after an authorized amendment is applied through the owning tools.

## Rationale

This is the smallest placement change that preserves the existing native admission model. It explicitly accepts losing mandatory separate cgroup isolation rather than replacing native login evidence with manager assertions. It is conditional because modern desktop autostart may itself run under a user-manager unit; a direct child does not manufacture a missing session mapping. Those profiles remain blocked pending a separately reviewed binding design.

## Consequences

Review can settle the placement tradeoff without changing security authority. Linux activation still requires a disposable graphical runner, native login/autostart proof, crash and logout lifetime proof, two distinct installed releases, package ownership and the existing upgrade/uninstall acceptance. If no supported desktop autostart profile can satisfy direct native admission and independent runtime lifetime together, reconsider the separate authenticated login-binding option. No accepted decision or release gate changes when this proposed record is created.

2026-10-08 native GNOME evidence in the linked research confirms the proposed direct-child option is insufficient for the observed default Ubuntu 24.04 GNOME autostart profile: the autostart process is under user@1000.service/app.slice and sd_pid_get_session returns ENODATA despite an active local X11 logind session. No eligible direct-child placement is established on this profile. This proposal remains unaccepted and does not justify Linux main activation; broader support would require a separately grounded native session-binding design or an installed launch profile that independently satisfies the existing authority and lifetime contract.
