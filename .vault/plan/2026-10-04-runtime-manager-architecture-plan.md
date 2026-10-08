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
  - '[[2026-10-08-canonical-environment-darwin-transport-adr]]'
modified: '2026-10-08'
body_schema: body-v2
body_hash: 'sha256:8084eea6e66fd371c9cdd2c2747e7c2ff0e1c1c45ae5535ea766cbee1ecbedbc'
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

2026-10-07 corrective authorization: the operator requested fixing the identified high, medium and low issues while retaining current binary placement and authority, then selected "Fix defects and the discovery blocker". P02.S09 repairs the three reproduced supervision defects. P03.S27 implements the already accepted stable-entry/versioned-install commitment across packaging, shared discovery, manager startup and desktop dispatch. This authorization includes those owning source areas; remaining tray, autostart, cutover/rollback and platform rollout are excluded. The existing format-specific upgrade, removal and disposable-host acceptance gates remain open.

2026-10-08 expanded authorization: the operator requested coding and building everything except signing certificates, which will not be available, and authorized dependency installation. This supersedes the earlier session limitation to defects and discovery: remaining installer, IPC/readiness, preferences, cutover/rollback, uninstall detection and platform source/build work are authorized. Produce unsigned artifacts and retain truthful platform/interactive acceptance limits; absence of signing must not be presented as completion of platform APIs requiring signed identity. No permission to publish, purchase certificates or treat a development host as a disposable acceptance machine is inferred.

## Steps

### Phase `P01` - Runtime supervisor contract

Runtime-side supervised mode, boot record, settle and exit reasons from the supervisor-contract ADR; runtime-owned source under src/cadrumo, with the --supervised flag passed through unchanged by the packaged binary.

- [x] `P01.S01` - Add the runtime exit-reason table with reserved ranges and project it to Rust through the contract generator; `src/cadrumo/application/runtime/contracts.py, contract generator projection, owning tests`.
- [x] `P01.S02` - Add the --supervised mode with private non-inheritable protocol streams, fd 0/1/2 rewired to null, hooks routed through redacted logging, and the ready/heartbeat/stopping protocol with ping/stop/stop-if-idle/session-end; `src/cadrumo/entrypoints/runtime/main.py, new supervised-channel module under src/cadrumo/entrypoints/runtime/, src/cadrumo/adapters/local_runtime/server.py, owning tests`.
- [x] `P01.S03` - Publish and remove the non-private boot record with custody local-record primitives and register it with the manager records in the storage taxonomy; `src/cadrumo/adapters/local_runtime/installation.py neighbour module, storage taxonomy owner, owning tests`.
- [x] `P01.S04` - Implement the ordered session-end settle: fence admissions, terminate and confirm the worker job, record ORPHANED or UNKNOWN and release only confirmed leases, then exit; `src/cadrumo/application/operations/_supervisor_drain.py, src/cadrumo/entrypoints/runtime/profile_connection_drain.py, owning tests`.
- [x] `P01.S05` - Re-enable Ctrl+C processing at startup, give non-worker children their own console under --supervised, and refuse a full elevated token under --supervised; `src/cadrumo/entrypoints/runtime/main.py, src/cadrumo/adapters/persistence/storage/custody/_kdf_process.py, src/cadrumo/adapters/outbound/browser_runtime/installer.py, owning tests`.
- [x] `P01.S06` - Rename manager_commands.py to containment_commands.py with NativeManagerCommand, ManagerCommandResult and run_manager_command_sync, updating all consumers atomically; `src/cadrumo/adapters/local_runtime/manager_commands.py, linux_worker_process.py, macos_worker_process.py, their tests and fixtures`.
- [x] `P01.S22` - Report exact in-flight operation counts from profile workers to the supervisor heartbeat and stop-if-idle, replacing the hosted-profile upper bound; `src/cadrumo/entrypoints/runtime/profile_connections.py, profile worker status request, supervised_channel.py, owning tests`.
- [x] `P01.S25` - Benchmark headless runtime startup and concurrent native connections; exercise malformed, stalled, disconnected and foreign-owner interference; fix measured in-scope runtime-management bottlenecks and preserve bounded admission and cleanup; `src/cadrumo/adapters/local_runtime/, src/cadrumo/entrypoints/runtime/tests/, native/manager/ targeted tests, benchmark evidence`.
- [x] `P01.S26` - Render React skeletons during asynchronous desktop runtime startup, settle to canonical Tauri readiness or bounded failure, and verify recovery and responsive navigation.; `native/desktop/frontend startup account hook, shared loading component, scenario fixtures and focused tests using existing Tauri manager dispatch and readiness`.

### Phase `P02` - Manager core on Windows

The cadrumo-manager native image: identity-derived names, canonical locations, supervision core, Windows stop and session-end handling, session ownership, IPC, tray, logs and preference.

- [x] `P02.S07` - Create the native/manager crate and cadrumo-manager root-level image with identity-projected names, the Background Services suffix owner, DEPENDENTLOADFLAG linkage, platform-mapping declaration, manifest, verification and signing inventory; `native/manager/ (new), native/CMakeLists.txt, native/cmake/, dev/packaging/native/identity.py, dev/packaging/native/ layout and verification, src/cadrumo/core/product_identity.py`.
- [ ] `P02.S08` - Consume the canonical location definition in strict profile through native/platform and probe storage identity and version from the installed interpreter; `native/manager/, native/platform/, native/application/ after desktop-shell S04-S07`.
- [x] `P02.S09` - Implement the supervision core with fixture test mode: launch with allow-list environment, readiness ceiling, heartbeat hang escalation, restart classes with monotonic backoff, crash-loop ceiling, adoption by image, elevation and boot record, and foreign state; `native/manager/, fixture runtimes in isolated synthetic roots`.
- [ ] `P02.S10` - Implement Windows stop delivery, the manager window procedure for session end with cancel restart and restart suppression, job escape, and elevation and session-0 refusal; `native/manager/ Windows modules`.
- [x] `P02.S11` - Implement session ownership: per-session lock, per-user kernel-released start claim and Quit marker conformance-tested against the Python custody primitives, observe-only other sessions and active-session handoff; `native/manager/, contract generator conformance tests`.
- [ ] `P02.S12` - Implement the manager IPC endpoint with owner and image verification and the closed reveal, retry and successor-readiness request set; `native/manager/`.
- [ ] `P02.S13` - Implement the tray surface, manager log and per-user preference with strings from the canonical locale catalogues; `native/manager/, src/cadrumo/locales/ via the dev.locales workflow`.
- [x] `P02.S23` - Gate supervisor restarts through the per-user start claim so an observing session cannot relaunch during the owner's backoff; `native/manager/src/supervision/supervisor.rs, native/manager/src/session/ownership.rs, owning tests`.
- [x] `P02.S24` - Register the manager .runtime records, preference and log locations in the Python storage taxonomy and record the session lock, start claim and Quit marker grammar as a cross-version contract; `src/cadrumo/core/storage_taxonomy.py, storage_taxonomy_locations.py, native/CONTRACT.md, owning tests`.

### Phase `P03` - Installation and client remedies

Windows login registration in the installation scope and client remedies that name the manager.

- [x] `P03.S27` - Resolve the audit's installed-version discovery blocker with a shared Windows versioned-prefix layout, complete-version catalogue and stable manager entry point consumed by packaging, manager startup and desktop dispatch; preserve root-level images, strict admission and existing process authority.; `dev/packaging/native installation/layout owners and tests, native/application shared discovery, native/manager startup, native/desktop manager target selection and owning tests`.
- [ ] `P03.S14` - Generate Windows login registration and the manager Start-menu shortcut with AUMID in both installation scopes from the identity projection, gated on the versioned-install layout; `dev/packaging/native/installation.py, native/cmake/distribution/`.
- [ ] `P03.S15` - Add localized UNAVAILABLE remedies naming the manager to CLI, TUI and MCP refusal output without automatic manager requests; `src/cadrumo/adapters/local_runtime/runtime_client.py consumers, src/cadrumo/locales/, src/cadrumo_harness/mcp/`.

### Phase `P04` - Version cutover

Manager-owned side-by-side cutover once the distribution workstream's versioned layout exists.

- [ ] `P04.S16` - Implement cutover orchestration with the held start claim, stop-if-idle, designated child successor, rollback and the failed-version marker; `native/manager/`.
- [ ] `P04.S17` - Implement this-user obsolete-version removal through the package manager and uninstall detection from the version-independent entry point; `native/manager/`.

### Phase `P05` - Linux and macOS

Platform ports deferred behind their prerequisites.

- [ ] `P05.S18` - Port the manager to Linux with XDG autostart in both scopes, systemd-run scope placement with probed pipe fallback, logind handling and StatusNotifier tray; `native/manager/, native/platform/ POSIX support, Linux packaging`.
- [ ] `P05.S19` - Implement and verify the macOS manager source and unsigned build, including canonical transient transport locations, session/process custody, IPC, lifecycle, bundle registration metadata and menu-bar integration; retain signing-dependent registration and disposable-host acceptance gates; `native/manager/, native/platform/, canonical core storage and native contract projection, macOS bundle packaging, focused owning tests`.

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

2026-10-05 lane dispatch: the operator authorized B5, followed by D1 and D2, with no lanes beyond B1-B5/D1-D2. B1-B4 remain external concurrent owners. B5 owns `native/manager/**`, starting at S23 and consuming B1 package contracts, B2 platform/environment APIs and B4 state/protocol declarations. Its first checkpoint checks B4-owned S04 ordered settle, S22 exact counts and S24 manager record schemas. S08/S10/S12/S13 advance only where prerequisites are available. Requests touching native/application, native/platform, packaging or locales go to those owners. The coordinator serializes this session's vault, ledger and commit writes and owns shared verification; workers use separate Cargo outputs. External B1-B4 agents are not visible here: shared files and supplied handovers establish their state.

B5 initial checkpoint (2026-10-05, shared working tree): `SupervisedController._end_session` still requests `SESSION_END_SETTLE` through the normal drain; the supervisor exposes Stop/StopIfIdle but no SessionEnd request. Python and Rust heartbeat still carry `hosted_profiles`, not exact operations. B4 must supply the final S04/S22 behavior and count contract before B5 changes that wire schema. Manager taxonomy entries are present in working changes; the current Rust Quit marker is `{schema_version: 1, session, user, set_at_ms}`, bounded to 4096 bytes, with ASCII identifier bounds and an integer timestamp up to 2^53-1. S24 remains open until B4 records and verifies the cross-version grammar. S23 restart-claim gating is independently ready; live manager integration is not claimed complete.

2026-10-08 execution assignment under expanded authorization: P02.S12 manager IPC may proceed while the distribution owner implements shared publication state. IPC ownership is native/manager IPC modules and their tests plus lib.rs/main.rs/windows_lifecycle.rs integration; the distribution owner retains native/application installation state, native/manager installation.rs/installed.rs lease consumption, native/desktop manager dispatch and packaging. Keep these writes disjoint. The root agent serializes vault edits, native Cargo verification/builds and commits; IPC work reports its source ready before a shared native build.

2026-10-08 continuation: the manager worker may continue P02.S13 and its P02.S24 storage prerequisite alongside root-owned distribution/native MSI and Linux build work. Worker owns manager tray/preferences/logging/IPC reveal integration, the canonical storage taxonomy entries and locale catalogue additions, plus focused tests. Root owns installer publication, native MSI adapter, packaging/CMake and vault checkpoints. Existing other-agent changes must be preserved. Coordinate native Cargo checks before running; source ownership is disjoint except root reviews.

2026-10-08 Linux continuation: P05.S18 may proceed on existing POSIX platform/custody code alongside the Windows tray and MSI lanes. A Linux worker owns new Linux manager backend modules and focused tests plus Linux-only service/desktop registration sources. Coordinate main.rs/lib.rs inclusion with the Windows manager owner instead of editing their ongoing startup changes. Root owns CMake Linux toolchain, configure/build and vault records; Linux native tests use the separate Linux binary directory. Do not enroll macOS signing-dependent acceptance or claim desktop/session acceptance from container checks.

2026-10-08 unsigned platform continuation: the operator explicitly requested all code/build work except signing certificates. Signing therefore does not block unsigned macOS source authoring and static/bundle checks for P05.S19; native Apple SDK/build and SMAppService acceptance still require their own evidence. The platform worker may own macOS LaunchAgent metadata authoring and focused tests plus a grounded account of unsigned SMAppService constraints while Windows cutover and MSI ownership remain with their existing workers. Coordinate any shared installation.py/CMake integration with root. Do not claim native macOS compilation or login acceptance without an Apple runner.

2026-10-08 continuation assignment: manager_remedies owns S16 connected-frontend upgrade notifications across the existing typed runtime session-event producer, verified transport demultiplexer, CLI binding, and TUI account/restricted shells, with focused tests. This work may run alongside msi_maintenance's S09 native transaction/publication protections because the owned source modules are disjoint. Check existing diffs before editing and preserve concurrent frontend work. Notifications convey no management authority or authentication retirement; delivery must be bounded and coalesced, distinguish enqueue from successful flush, and preserve legacy-client protocol compatibility. Root owns integration, verification coordination, vault records, and commits. Interactive two-release acceptance remains required.

2026-10-08 S17 launch-fence correction: manager_remedies owns the shared exact-current-package Ready/lease admission API in native/application, a narrow native/launch_guard static C ABI crate/header, and desktop Launch lifetime custody with focused tests. Root owns C interpreter host calls and CMake static-library orchestration. msi_maintenance continues native transaction-owner records and safe removal; it must not treat RM snapshots as launch exclusion before these entry boundaries participate. Coordinate any maintenance.rs changes with its installer owner. Keep the existing platform/application dependency direction: the new ABI bridge may depend on application but platform must not depend cyclically on it. Missing native marker/publication for a structurally versioned package is refusal, never a portable fallback. Every Python child independently holds its own package lease through process lifetime; no Python/environment bypass grants admission. Root owns combined verification, source snapshots, vault and commits.

2026-10-08 unsigned S19 source assignment: the linux_manager worker, after releasing its completed Linux IPC/SDK lane, owns a bounded macOS process-identity foundation in new native/manager/src/macos.rs, macos/records.rs and macos/process.rs, plus the minimal lib.rs export. Reuse the existing runtime's guarded native audit-token/libproc identity contract and retained kqueue exit observation; no numeric-PID signaling fallback, signing substitute or manager-main activation. Pure record/identity tests and source formatting may run on available hosts; native macOS compilation and behavior remain unverified without the Apple SDK/runner. This disjoint source slice may run alongside S09 installer recovery. Root owns shared CMake/build lanes, integrated review, vault and commits.

2026-10-08 S19 continuation: linux_manager may add macos/login.rs and its macos.rs export, reusing the runtime's existing kernel LOCAL_PEERTOKEN/LOCAL_PEERPID and Security.framework SessionGetInfo policy for peer/session observation. Preserve held-process incarnation checks, unavailable/absent distinctions and unknown lock/console state. No manager self-session API, shared-session/main activation or signing-dependent registration is included in this slice. Root retains shared builds, vault and commits; coordinate native Cargo checks with the installer owner.

2026-10-08 native build corrections: msi_maintenance, after completing its committed installer recovery checkpoint, may own the reproduced Linux socket-permission compatibility defect in src/cadrumo/adapters/local_runtime/posix_endpoint.py and focused owning tests. The glibc-2.28 builder's real CPython raises NotImplementedError for chmod(follow_symlinks=False); preserve no-follow identity/custody and do not introduce a pathname-following fallback or process-wide umask mutation. Root owns docs scratch propagation and frozen-source/full-build orchestration. linux_manager may correct the shared Python macOS login observer and Rust macos/login.rs known-flag validation after primary Apple evidence: SessionGetInfo returns native audit flags including SDK-documented 0x2000 and 0x4000. Recognize those documented bits without granting active/unlocked/unattended eligibility, keeping root/remote/non-graphical refusal. Coordinate tests and preserve all other native source edits; root owns vault and commits.

2026-10-08 native Mac verification correction: linux_manager also owns the two narrow Linux-only effective_uid cfg guards in custody.rs and custody/posix.rs after proving all callers are Linux-gated; native Mac all-target Clippy verifies the correction. msi_maintenance may provision an isolated docs build under the existing WSL user's build directory and execute the synthetic docs fixture using its already-running user-systemd containment. Do not change services, install the product, register login, reboot or weaken native containment. Root retains repository docs/CMake edits, snapshot provenance, vault and commits. Both named Windows and macOS hosts are non-disposable and restricted to isolated builds and non-destructive probes.

2026-10-08 S19 IPC continuation: linux_manager may implement a bounded native Darwin manager transport module and minimal macos.rs export, reusing the existing held-process and kernel peer-session foundation plus existing POSIX custody patterns. Preserve owner-only anchored sockets, exact process incarnation, bounded framing and fail-closed peer/session observation; no numeric-PID fallback, global signal policy change or manager-main activation. Avoid broad shared transport refactors without root coordination. Verify with an isolated native Mac test crate/build so ongoing frozen package inputs stay unchanged. Root owns shared contracts, source integration decisions, reviews, vault and commits; host registration/install/session-ending tests remain excluded.

Darwin IPC continuation: the existing linux_manager worker also owns the narrow platform-neutral bounded framing extraction into native/manager/src/ipc/framing.rs, minimal ipc.rs and Linux IPC caller/test changes, and macos/login.rs current-process identity capture using Mach TASK_AUDIT_TOKEN corroborated with held Process and Security SessionGetInfo. Preserve native incarnation, same-user and graphical-session authority; no environment or PID-only fallback. Retest shared framing on Linux and Darwin. Keep main activation gated and the ongoing frozen Mac package source untouched. Root owns review, plan/audit edits and commits.

2026-10-08 S19 shared session continuation: after a read-only status check of the original blockers, linux_manager owns the narrow macOS ManagerSession::current and shared current-session observation integration using the existing held Process and kernel-backed Login::current. Preserve graphical-session refusal, unknown activity state, exact incarnation checks and main/registration gates. Ownership is session.rs, supervision/process.rs and a narrowly scoped macOS session helper/tests if needed. No adoption, signaling, instance activation or new session authority is included. Root owns integrated review, vault records and commits; native Mac validation remains pending connectivity, and active frozen build inputs must stay unchanged.

2026-10-08 S19 socket-path investigation: linux_manager owns bounded read-only canonical location/projection analysis and a candidate amendment draft; notice_review owns primary Apple API comparison, one isolated /dev/fd alias probe, and evidence consistency review. Root owns research, audit, decision reconciliation and any later source assignment. No namespace change, private API, global working-directory mutation or product-directory creation is authorized by these research assignments. The installed-default path defect keeps platform activation gated.

2026-10-08 S19 Darwin transport implementation assignment: under the operator's all-code/build authorization, linux_manager owns the canonical Python transport declaration, lazy location resolution, taxonomy materialisation/reclaim semantics, runtime endpoint and synthetic-fixture integration, native generator projection and conformance vectors, and focused owning tests. Root owns the Rust platform transport resolver, manager compact naming and IPC consumption, native checks, integration review, vault records and commits. notice_review owns the reviewed decision and four prior-ADR reconciliations before source work. Installed Darwin mode without an explicit namespace/member override uses the native transient anchor regardless of inherited storage-root pin; root-derived leaves preserve custom-root and channel identity separation. Development and explicit synthetic namespace isolation remain. No new environment pin or channel inference is introduced. Existing frozen package inputs remain unchanged. Native checks use synthetic directories; no product installation, login registration or session-ending acceptance occurs on these non-disposable hosts.

2026-10-08 S19 instance-ownership continuation: linux_manager owns the bounded Darwin session-lock/IPC capability integration in session/instance.rs, macos/ipc.rs and macos/ipc/socket.rs, with a narrowly scoped helper/test module if needed. Reuse the canonical compact socket name and its existing persistent namespace-lock inode; acquire once and retain explicit custody across server lifetime without implicit reacquisition or premature release. Verify owner/mode/inode and namespace replacement refusal, current native session binding, contention and cleanup with synthetic native tests. Preserve non-Darwin behavior and keep manager-main activation, product registration and graphical acceptance gated. Root owns final implementation review, native build snapshots, shared Cargo runs, vault records and commits. Frozen package builds remain unchanged; discovery uses bounded named-file inspection while the semantic service is unavailable.

2026-10-08 S19 Darwin supervision continuation: following the isolated native task-name/audit-token proof, linux_manager owns Login::process in macos/login.rs, Darwin held-process inspection/adopted exit and stop integration in supervision/process.rs and supervision/stop.rs, plus narrowly needed held-process formatting and focused tests. Reuse task_name_for_pid with a retained/deallocated task-name send right, TASK_AUDIT_TOKEN, exact UID/PID/pidversion checks and existing Security session policy. Keep ambiguous Mach permission failures distinct from proven process absence; do not use task_for_pid, POSIX session IDs, environment or fabricated audit-session authority. Native signal/exit tests may target only synthetic children launched by that test and must reap them; never signal existing host processes or change host sessions. Root owns shared native builds, review, source snapshots, vault and commits. Manager-main, login registration, native graphical acceptance and existing frozen package inputs remain gated/unchanged.

2026-10-08 S19 activity observation: linux_manager owns macos/activity.rs and macos.rs enrollment plus owning tests. Use public caller-scoped CGSessionCopyCurrentDictionary. Retain a fully admitted current Process and native Session; bracket each query with unchanged kernel UID/ASID and require strictly typed matching UID, OnConsole and LoginDone values. Missing or inconsistent evidence remains unavailable; only corroborated on-console and logged-in state grants start/restart eligibility. No undocumented keys, console-set/ASID conflation, unlocked-state claims or session-end signals. Native checks only observe the SSH host or synthetic pure-policy fixtures. Main activation, lifecycle/registration and frozen package inputs stay unchanged. Root owns native suite snapshots, review, vault and commits.

2026-10-08 S19 lifecycle prerequisite: linux_manager owns a behavior-preserving extraction of the existing pure lifecycle and cutover-runtime traits from windows_lifecycle.rs/cutover_coordinator.rs into their canonical shared owner, with atomic consumer/test imports and lib.rs enrollment. Preserve Background's concrete Windows gating and all existing method semantics, cutover cancellation, claims and settlement behavior; do not add no-op platform adapters or activate another platform. Move existing trait implementations without public re-export compatibility aliases. This prerequisite gives later native hosts the same lifecycle contract while actual platform composition remains gated. Root owns reviews, shared Windows/Mac checks, vault and commits; unrelated peer source work is excluded.

2026-10-08 S19 portable Background prerequisite: linux_manager owns the sealed shared successor permit/reporting owner with nested Windows-only native admission, required-method installation-removal observation contract with the existing Windows watcher implementation, and minimal Background/startup/supervised/lifecycle/lib/main consumer changes to compile the existing state machine on supported platforms. Preserve private permit construction after native admission, exact root/session/Quit checks, bounded reporting and final Ready acknowledgement, retained claims, cancellation and settlement semantics. No no-op macOS removal watcher, new authority constructor, native activation, installation-layout decision or host mutation. Root owns shared Windows/Mac verification, integrated review, vault and commits. Keep frozen builds and unrelated peer edits unchanged.

2026-10-08 S19 nonblocking session-end prerequisite: linux_manager owns startup.rs, background.rs, lifecycle.rs and the minimal Windows lifecycle test consumer updates for required begin_session_end/session_end_settled methods. Suppress restarts before the stop request, keep repeated notifications idempotent without extending stop deadlines or writing user Quit preferences, and preserve the existing Windows 3500ms bounded wrapper. Nonblocking settlement must retain terminal evidence until the real worker finishes, join it and drain final events before successful completion; disconnection, panic and errors cannot masquerade as clean settlement or discard ownership. Add focused tests for result-before-thread-exit, clean join, disconnection/panic, repeated requests and cancellation/reassessment. No native host activation, signal registration, new installation policy or frozen-build modification. Root owns shared checks, integrated review, vault and commits.

2026-10-08 S19 native AppKit host slice: linux_manager owns new macos/lifecycle.rs and narrowly scoped lifecycle helper/tests, macos.rs enrollment, target-specific Cargo.toml dependencies and resulting Cargo.lock. Implement a typed main-thread NSApplicationDelegate/retained observer and timer using existing objc2 versions, consuming the real shared ManagerLifecycle nonblocking shutdown contract and retaining supplied native custody through settlement. Public power-off/logout and Tokio SIGTERM observations suppress restart; deferred termination polling includes NSModalPanelRunLoopMode. Preserve user Quit separation, repeated request idempotence, unknown effect semantics, and explicit failure retention. Do not infer logout cancellation from activation or console activity; no no-op cutover owner, fabricated IPC readiness, production main activation, login registration, or graphical/session-ending host probe. Main integration remains gated on real native installation/cutover ownership and cancellation acceptance. Dependencies resolve through normal Cargo, no hand-authored lockfile edits. Root owns source review, native compile/tests, snapshot provenance, vault and commits; frozen package builds and peer edits remain unchanged.

2026-10-08 S19 native status-menu continuation: after completing the verified unsigned DMG, linux_manager owns an inactive typed AppKit status-menu adapter and narrowly required canonical manager menu model/effect traits, macos.rs/lifecycle enrollment and target-specific manager Cargo dependency/lock changes. Reuse existing canonical Strings, Preferences and real Background/lifecycle semantics. Required effect methods must represent native open-application/logs/login actions and refuse cutover-busy operations; no no-op defaults, fabricated native registration, main activation or UI/session mutation on the personal Mac. Implement and test pure menu projection/action policy and compile the real adapter in an isolated native Mac source snapshot. No edits to native/application, native/platform, native/installer or native/cmake while root's full MSI input verification is active. Root owns shared contract approval, integrated review, governance and commits. Remaining native installation layout/publication/cutover decisions and host acceptance gates remain explicit.

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
