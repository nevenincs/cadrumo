---
tags:
  - '#adr'
  - '#runtime-without-service-manager'
date: '2026-10-03'
modified: '2026-10-03'
body_schema: 'body-v2'
body_hash: 'sha256:0f47f4cfe6c43b4d3a4918cb8eca27e2664fb0b84ce90535b730e41787070c5e'
related:
  - "[[2026-09-26-mcp-purpose-authentication-adr]]"
  - "[[2026-09-26-mcp-purpose-authentication-profile-access-adr]]"
  - "[[2026-09-26-mcp-purpose-authentication-reference]]"
  - "[[2026-09-26-mcp-purpose-authentication-research]]"
  - '[[2026-10-03-runtime-manager-architecture-research]]'
---
# `runtime-without-service-manager` adr: runtime management is deferred to application provisioning | (**status:** `accepted`)

## Problem Statement

The shared local runtime owns authenticated IPC, profile custody and application execution. Installation and health management were incorrectly added to that runtime feature before application bundling, building and provisioning were designed.

On 2026-10-03 the operator explicitly authorized amending the runtime and related ADRs to exclude all runtime management, removing its code and wording, and preserving the runtime itself. This ruling includes all platforms and management branches embedded in otherwise retained runtime modules.

## Considerations

The existing runtime already has a standalone entrypoint and verified endpoint. Its sealed interpreter, single-owner exclusion, profile admission, custody and worker containment do not require runtime administration controls. Evidence is in 2026-09-26-mcp-purpose-authentication-reference and 2026-10-03-runtime-manager-architecture-research. Those records retain historical observations; they do not authorize management implementation.

The code inspection identified management in `src/cadrumo/adapters/local_runtime/startup.py`, `runtime_manager_composition.py`, the platform manager adapters, `src/cadrumo/entrypoints/runtime_management.py`, CLI runtime commands, TUI management screens, and owner-control/status transport requests. Removing only registration would leave health management in place and would not implement the operator's instruction.

## Considered options

- Retain health and start/stop controls after removing registration: rejected; these remain runtime management.
- Replace registration with frontend spawning, idle-exit policy or a new supervisor: deferred; these require the later application bundling, building and provisioning design.
- Remove management throughout the product while preserving the runtime and its security/resource boundaries: selected.

## Constraints

Runtime management is outside the runtime's scope. No service installation or registration, enable/disable controls, global start/stop/status administration, health dashboard or probe API, autostart, repair, restart supervision or upgrade orchestration belongs to this implementation. Remove their modules, mixed-file branches, contracts, settings, locale keys, tests and documentation without aliases or unreachable remnants.

Preserve the runtime executable, isolated bootstrap, verified local IPC and handshake, single-owner convergence, profile authentication and session/grant administration, operation observation, encrypted custody, login provenance, safe shutdown and descendant containment. Handshake compatibility checks and typed connection failures remain necessary transport behavior. Operation supervision and profile/session status are not runtime health management.

Transient worker containment remains part of runtime safety, including native Job Objects and Linux transient worker scopes. Login observation remains an admission input. Neither authorizes persistent runtime registration or a health-management interface.

Scheduled tasks are unsupported, including temporary testing, authentication, desktop-session bridges and recovery workarounds. Do not create, register, run or recreate them. There is no provisioned runtime application at present; developers manage the runtime manually for testing. Missing desktop access or an unavailable runtime must be reported, never worked around through OS registration.

Application bundling, building and provisioning will decide the runtime launch and management policy later. Until then clients connect to an explicitly started runtime and report typed unavailability when no verified endpoint exists. This decision adds no automatic spawn or replacement manager.

The operator authorized an explicit development session override on 2026-10-03. Core Settings owns `CADRUMO_DEV_RUNTIME_SESSION_OVERRIDE`; exactly `1` replaces native desktop/login-session admission with a same-account, runtime-boot-scoped development lifetime. The default setting is strict; the development environment template explicitly enables the override. The runtime selects the policy at startup, not from client requests. Native peer ownership, endpoint/version/storage identity, profile credentials, API-key grants, connection/session authorization, encrypted custody and worker containment remain mandatory. Stop or runtime replacement retires the development lifetime. Runtime integration and CLI/MCP fixtures explicitly opt in through this same policy; native session-policy tests keep strict admission. This override does not launch or register any runtime.

## Implementation

Apply focused amendments to 2026-09-26-mcp-purpose-authentication-adr and 2026-09-26-mcp-purpose-authentication-profile-access-adr. Remove their management commitments and parity requirements while preserving the other accepted decisions. Reconcile open implementation-plan scope against this ruling.

Delete management-only modules and their consumers. In shared runtime modules remove only administration/provisioning dispatch and arguments, retaining security and cleanup behavior. Remove the runtime administration command family and TUI health controls. Remove public owner-stop and health request/reply contracts while retaining internal shutdown and transport authentication. Update fixtures to own explicitly launched test processes and close them through their test-owned lifetime.

Verify the live source inventory for residual management APIs, imports, UI actions, configuration and documentation. Run focused transport, client, CLI and TUI checks plus lint/type/import-boundary and generated-reference checks. No removal is complete merely because a management branch is unreachable. Existing machine registrations are outside this repository change; no product unregister mechanism is retained.

Development and automated testing may explicitly own runtime lifetimes. Integration and end-to-end fixtures may automatically start a runtime in an isolated synthetic storage root, await the existing verified transport handshake with a bounded deadline, and stop and reap their owned processes in teardown, including assertion failure and cancellation paths. This is test resource ownership, not product runtime management; it adds no service registration, public health endpoint, restart supervision or frontend autostart. Fixtures must not reuse or stop an unrelated developer runtime. Pure unit tests need no background runtime. Manual client testing requires an explicitly started matching runtime; the developer session owns its cleanup.

## Rationale

Runtime hosting and admission need a secure process boundary. Runtime management needs an application distribution and provisioning design. Combining them prematurely created OS state and product controls without that design. Removing management restores the intended boundary without replacing the runtime.

## Consequences

The runtime remains the shared execution and custody authority. Clients require a running runtime until provisioning defines launch policy. Profile authentication, grant/session administration and operation visibility remain available through that boundary.

The earlier service-installation and health-management approach is withdrawn. Management is deferred, not permanently prohibited: reconsider it only with application bundling, building and provisioning. Acceptance records the operator-authorized scope; code removal and cross-platform verification must be reported separately.
