---
tags:
  - '#plan'
  - '#runtime-manager-architecture'
date: '2026-10-04'
tier: L2
related:
  - '[[2026-10-04-runtime-manager-architecture-adr]]'
  - '[[2026-10-04-runtime-manager-architecture-supervisor-contract-adr]]'
  - '[[2026-10-04-canonical-environment-adr]]'
  - '[[2026-10-04-desktop-shell-adr]]'
modified: '2026-10-05'
body_schema: body-v2
body_hash: 'sha256:9b3c0404ef77ff6217c859a0ed37516934fb7ab2a7fddd198ec2d482409d6165'
---

# `runtime-manager-architecture` plan

## Description

Approved 2026-10-04. Basis: the operator's "Approved! go" in response to the presentation of this plan and its sibling plan.

Implements the per-user runtime manager and the runtime supervisor contract. On 2026-10-04 the operator approved both governing ADRs and `2026-10-04-canonical-environment-adr` ("all approved!").

Decision coverage: no new costly decision is needed. The scope of each ADR maps onto the phases as follows:

- `2026-10-04-runtime-manager-architecture-supervisor-contract-adr` governs P01.
- `2026-10-04-runtime-manager-architecture-adr` governs P01.S06 (naming hygiene) and P02 through P06.
- `2026-10-04-canonical-environment-adr` governs P02.S08 (locations, strict profile) and the storage-root prerequisite.
- `2026-10-04-desktop-shell-adr` bounds the desktop seams consumed in P02.S12 and P03, but the desktop-side steps belong to the desktop-shell plan.

External prerequisites, owned elsewhere, gate specific steps:

- **Canonical-environment implementation** (desktop technical workstream). P02.S08 and every shipping step depend on it.
- **The versioned-install layout per installer format** (distribution workstream, CADRUMO-BUILD-RUNTIME as packaging owner). P03.S14, P04 and shipping on a format depend on it. The manager does not ship for a format until that layout is implemented and passes acceptance.
- **Desktop-shell S04-S07 must land** before the Settings projection moves into `native/application` in P02.S08.
- **The POSIX build of `native/platform`** gates P05.S18. Signing credentials gate P05.S19.

Ownership:

- P01 is runtime-side source. CADRUMO-BUILD-RUNTIME declined it and needs only notice of any runtime CLI or handshake change, so that its verifier's runtime probe stays correct.
- Locale strings go through the `dev.locales` workflow.
- Tests never register login start. Package acceptance runs only on disposable hosts.

Named follow-on decisions remain outside this plan:

- whether an UNKNOWN login inventory should stop an idle runtime
- whether installed-image override refusal should be adopted
- whether elevation refusal should be unconditional
- per-session admission versus attended-session lifetime
- how MCP-originated approval prompts are surfaced

## Steps

### Phase `P01` - Runtime supervisor contract

Runtime-side supervised mode, boot record, settle and exit reasons from the supervisor-contract ADR; runtime-owned source under src/cadrumo, with the --supervised flag passed through unchanged by the packaged binary.

- [x] `P01.S01` - Add the runtime exit-reason table with reserved ranges and project it to Rust through the contract generator; `src/cadrumo/application/runtime/contracts.py, contract generator projection, owning tests`.
- [x] `P01.S02` - Add the --supervised mode with private non-inheritable protocol streams, fd 0/1/2 rewired to null, hooks routed through redacted logging, and the ready/heartbeat/stopping protocol with ping/stop/stop-if-idle/session-end; `src/cadrumo/entrypoints/runtime/main.py, new supervised-channel module under src/cadrumo/entrypoints/runtime/, src/cadrumo/adapters/local_runtime/server.py, owning tests`.
- [x] `P01.S03` - Publish and remove the non-private boot record with custody local-record primitives and register it with the manager records in the storage taxonomy; `src/cadrumo/adapters/local_runtime/installation.py neighbour module, storage taxonomy owner, owning tests`.
- [ ] `P01.S04` - Implement the ordered session-end settle: fence admissions, terminate and confirm the worker job, record ORPHANED or UNKNOWN and release only confirmed leases, then exit; `src/cadrumo/application/operations/_supervisor_drain.py, src/cadrumo/entrypoints/runtime/profile_connection_drain.py, owning tests`.
- [x] `P01.S05` - Re-enable Ctrl+C processing at startup, give non-worker children their own console under --supervised, and refuse a full elevated token under --supervised; `src/cadrumo/entrypoints/runtime/main.py, src/cadrumo/adapters/persistence/storage/custody/_kdf_process.py, src/cadrumo/adapters/outbound/browser_runtime/installer.py, owning tests`.
- [x] `P01.S06` - Rename manager_commands.py to containment_commands.py with NativeManagerCommand, ManagerCommandResult and run_manager_command_sync, updating all consumers atomically; `src/cadrumo/adapters/local_runtime/manager_commands.py, linux_worker_process.py, macos_worker_process.py, their tests and fixtures`.
- [ ] `P01.S22` - Report exact in-flight operation counts from profile workers to the supervisor heartbeat and stop-if-idle, replacing the hosted-profile upper bound; `src/cadrumo/entrypoints/runtime/profile_connections.py, profile worker status request, supervised_channel.py, owning tests`.

### Phase `P02` - Manager core on Windows

The cadrumo-manager native image: identity-derived names, canonical locations, supervision core, Windows stop and session-end handling, session ownership, IPC, tray, logs and preference.

- [x] `P02.S07` - Create the native/manager crate and cadrumo-manager root-level image with identity-projected names, the Background Services suffix owner, DEPENDENTLOADFLAG linkage, platform-mapping declaration, manifest, verification and signing inventory; `native/manager/ (new), native/CMakeLists.txt, native/cmake/, dev/packaging/native/identity.py, dev/packaging/native/ layout and verification, src/cadrumo/core/product_identity.py`.
- [ ] `P02.S08` - Consume the canonical location definition in strict profile through native/platform and probe storage identity and version from the installed interpreter; `native/manager/, native/platform/, native/application/ after desktop-shell S04-S07`.
- [x] `P02.S09` - Implement the supervision core with fixture test mode: launch with allow-list environment, readiness ceiling, heartbeat hang escalation, restart classes with monotonic backoff, crash-loop ceiling, adoption by image, elevation and boot record, and foreign state; `native/manager/, fixture runtimes in isolated synthetic roots`.
- [ ] `P02.S10` - Implement Windows stop delivery, the manager window procedure for session end with cancel restart and restart suppression, job escape, and elevation and session-0 refusal; `native/manager/ Windows modules`.
- [ ] `P02.S11` - Implement session ownership: per-session lock, per-user kernel-released start claim and Quit marker conformance-tested against the Python custody primitives, observe-only other sessions and active-session handoff; `native/manager/, contract generator conformance tests`.
- [ ] `P02.S12` - Implement the manager IPC endpoint with owner and image verification and the closed reveal, retry and successor-readiness request set; `native/manager/`.
- [ ] `P02.S13` - Implement the tray surface, manager log and per-user preference with strings from the canonical locale catalogues; `native/manager/, src/cadrumo/locales/ via the dev.locales workflow`.

### Phase `P03` - Installation and client remedies

Windows login registration in the installation scope and client remedies that name the manager.

- [ ] `P03.S14` - Generate Windows login registration and the manager Start-menu shortcut with AUMID in both installation scopes from the identity projection, gated on the versioned-install layout; `dev/packaging/native/installation.py, native/cmake/distribution/`.
- [ ] `P03.S15` - Add localized UNAVAILABLE remedies naming the manager to CLI, TUI and MCP refusal output without automatic manager requests; `src/cadrumo/adapters/local_runtime/runtime_client.py consumers, src/cadrumo/locales/, src/cadrumo_harness/mcp/`.

### Phase `P04` - Version cutover

Manager-owned side-by-side cutover once the distribution workstream's versioned layout exists.

- [ ] `P04.S16` - Implement cutover orchestration with the held start claim, stop-if-idle, designated child successor, rollback and the failed-version marker; `native/manager/`.
- [ ] `P04.S17` - Implement this-user obsolete-version removal through the package manager and uninstall detection from the version-independent entry point; `native/manager/`.

### Phase `P05` - Linux and macOS

Platform ports deferred behind their prerequisites.

- [ ] `P05.S18` - Port the manager to Linux with XDG autostart in both scopes, systemd-run scope placement with probed pipe fallback, logind handling and StatusNotifier tray; `native/manager/, native/platform/ POSIX support, Linux packaging`.
- [ ] `P05.S19` - Port the manager to macOS with the SMAppService agent plist, process-group abandonment and menu-bar item once signing exists; `native/manager/, macOS bundle packaging`.

### Phase `P06` - Acceptance and review

Package acceptance on disposable hosts and integrated review against both ADRs.

- [ ] `P06.S20` - Run package acceptance on disposable hosts for every ADR acceptance obligation and record platform limits; `disposable Windows hosts, feature audit`.
- [ ] `P06.S21` - Review the integrated manager, runtime contract and installers against both ADRs and record findings; `feature audit`.

## Parallelization

- P01 and P02.S07 can run in parallel. P02.S09 and the steps after it consume P01's protocol and exit table, so they start once P01.S01 and P01.S02 have landed.
- P01.S06 is independent and can land at any time.
- P03.S15 can run in parallel with P02.
- P03.S14 and P04 wait for the external versioned-install layout.
- P05 waits for its platform prerequisites. P06 runs last.

Write ownership is disjoint:
- P01 touches `src/cadrumo/**` runtime modules.
- P02 and P04 touch `native/manager/`.
- P03 touches packaging generation and client remedies.

Coordinate any `native/application` or `native/platform` edits with the desktop-shell and packaging owners. Commit by pathspec, because the worktree is shared.

## Verification

**P01:**
- Focused runtime tests prove:
  - supervised readiness, heartbeat and stop-if-idle
  - a descendant cannot see the channel, and a stray stdout or stderr write cannot corrupt it
  - a broken pipe changes no exit code
  - every exit reason, including reserved codes, is distinguished
  - the ordered settle releases only confirmed leases
  - Ctrl+C re-enables after an inherited ignore
  - an elevated token is refused under --supervised
- Unsupervised launch and the packaged runtime probe are unchanged.

**P02 through P04:**
- Manager fixture tests in isolated synthetic roots cover each supervision class: crash, hang, outside stop, witness loss, foreign, stale and forged boot records, failed cutover with rollback, multi-session claim and Quit.
- Conformance tests cover the Rust lock, the record I/O and the exit table against the Python owners.
- Release builds refuse the test mode, and development builds never register login start.

**P06:**
- Disposable-host acceptance covers every obligation listed in `2026-10-04-runtime-manager-architecture-adr`, including platform questions still open in the research record.

**Every step:**
- The project's lint, format, type and import-boundary checks pass, plus `vault check all`.

**Completion:**
- The plan is complete when every step is closed and the integrated review in P06.S21 passes against both ADRs.
- Phase-close reviews apply at L2. Pending acceptance on platforms is reported separately from code defects.
