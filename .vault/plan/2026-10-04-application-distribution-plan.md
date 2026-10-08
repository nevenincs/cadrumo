---
tags:
  - '#plan'
  - '#application-distribution'
date: '2026-10-04'
tier: L1
related:
  - '[[2026-10-04-application-distribution-adr]]'
  - '[[2026-10-03-application-packaging-interpreter-foundation-adr]]'
  - '[[2026-10-03-runtime-without-service-manager-adr]]'
  - '[[2026-10-07-application-distribution-windows-versioned-msi-adr]]'
modified: '2026-10-08'
body_schema: body-v2
body_hash: 'sha256:9f336e24ceed8ee87e62b6ca9a2ab5937cbd85966d54475036f730df7d30cba2'
---

# Application distribution

## Description

Approved 2026-10-04

The user explicitly requested implementation of product identity, modern CMake configuration, native installation and uninstall across Windows, Linux and macOS. The accepted application-distribution ADR governs identity and installer contracts. The interpreter-foundation and storage decisions continue governing runtime isolation. The accepted runtime-manager-architecture decision extends the earlier without-service-manager deferral with a per-user manager and scoped login registration; SCM services and scheduled tasks remain excluded. Existing application-core work owns native backend provisioning and Rust internals; actual cross-platform release proof depends on that work and suitable runners.

2026-10-07 authorization and recovery: the operator requested resolving the Google ADR validation error and completing installer/upgrade acceptance, then directed continued work. The Google error is repaired separately. Current Windows source/template review demonstrates that the combined MSI's major-upgrade policy violates preservation of prior in-use versions, and only perMachine is authored; S03 is reopened by this high finding. S04 remains open. The concrete Windows installer ownership decision is 2026-10-07-application-distribution-windows-versioned-msi-adr. The operator directed continued installer and upgrade execution after the format-setup report and prior presentation of this proposal; its two-role MSI ownership design is now accepted. Execute cohesive role/scope identity, product authoring, transaction/scope admission and safe maintenance Steps before closing S03. Required source/host evidence remains in 2026-10-04-application-distribution-audit.

Live Windows acceptance also depends on manager-owned IPC, scoped default login start and opt-out, designated-successor cutover/rollback and uninstall detection in runtime-manager-architecture P02.S12-S13, P03.S14 and P04.S16-S17. Current source discovery does not complete those Steps. A disposable interactive Windows runner and two genuine distinct release payloads are required; development hosts receive no MSI, login registration or session-ending acceptance. Other target native backends, installation ownership and signing remain explicit gates rather than covered by the Windows proposal.

2026-10-07 format selection: the operator specified Windows MSI and macOS DMG and authorized setting them up now. Linux uses DEB and RPM through the existing accepted application-distribution decision. S06 exposes these as native default outputs and independently selectable build targets/presets, while ZIP remains explicit auxiliary delivery. This format setup executes under accepted authority and does not depend on the proposed Windows product-ownership protocol. S03/S04 retain their separate ownership and live acceptance gates.

2026-10-07 S07/S08 checkpoint: role/scope/release ownership identities and all four verified-stage WiX source definitions are implemented. The canonical CMake graph exposes msi-author and its cleanup; both the build target and direct CPack route refuse the unsafe combined manager MSI. The source definitions deliberately retain a literal-false install condition until S09 implements native transaction publication, scope admission, same-version byte checks, anchor retention and startup/removal exclusion. WiX 5.0.2 compiled and decompiled all four roles/scopes for desktop and runtime-only synthetic payloads, with warnings treated as errors; this establishes source/database authoring, not live release acceptance. S08 can close on that scoped evidence. S09 and the cross-plan manager lifecycle dependencies remain open implementation work. Its scope work must carry typed user/machine registration origin through the shared catalogue so the accepted this-user fallback is enforceable; the present untyped prefix list selects the globally newest valid version. No native product was installed.

2026-10-07 S10 correction: the Windows registry adapter now returns named this-user and all-users origins, and manager/desktop convert them to the shared catalogue's borrowed RegistrationHints. A verified this-user prefix outranks newer machine/local fallback prefixes. Invalid user candidates permit fallback; a local archive receives no user-scope preference without matching native registration. Native application/manager CTests, all nineteen selected desktop manager backend tests and pinned Rust 1.96 Clippy for all three consumers pass. This corrects the audit's scope-selection finding without implementing S09's all-account MSI admission or publication/removal exclusion. S09 is the next source implementation Step; S03/S04 and manager lifecycle dependencies remain open.

2026-10-08 CMake orchestration: the operator requested integrating the installation steps into the CMake-owned flow while preserving software and acceptance gates. S11 refines that authorized build integration: the manager msi target builds the four scoped products, msi-verify checks their source/payload/artifact bindings, and check-msi-installation fails with the unresolved lifecycle and disposable-runner requirements. A read-only native MSI database query verifies actual action sequencing because WiX 5.0.2 decompilation reconstructs the registration schedule inaccurately. Neither the source launch condition nor the readiness refusal is bypassable by a CMake switch. S09, S03 and S04 remain open; compilation receipts are build evidence and are not native transaction publication or install/upgrade acceptance. Linux/macOS native backends, runner evidence and release signing/notarization remain separate prerequisites.


2026-10-08 frozen acceptance correction: the unchanged Windows Modelo390 annual seed fails at fourth-quarter Modelo303 local filing because the registered CLI operation is still running when its shared 60-second deadline expires. Filing lacks the distinct settlement allowance already used by calculation and verification. S14 applies the existing bounded 1800-second settlement policy while retaining 60-second per-exchange bounds and existing unknown-effect/no-replay behavior. This is an in-scope installer-build blocker correction under the operator's continued implementation authorization; it introduces no transport, storage or installation authority change. The original long-work bottleneck remains unmeasured, and the separate Renta intermittent result-read failure remains unresolved.

## Steps

- [x] `S01` - Generate canonical product publisher channel and platform identities for all supported targets; `src/cadrumo/core/product_identity.py and dev/packaging/native/identity.py`.
- [x] `S02` - Project canonical identity into CMake project and platform packaging configuration; `CMakeLists.txt and native/cmake`.
- [x] `S06` - Expose native MSI, DMG and DEB/RPM delivery targets and presets with archives as explicit auxiliary outputs; `native/cmake/distribution, dev/packaging/native/tests/test_distribution_prepare.py and native/CONTRACT.md`.
- [x] `S07` - Separate Windows MSI product and component identities by ownership role, installation scope and release without changing legacy identities; `dev/packaging/native/identity.py, dev/packaging/native/windows_msi_identity.py and dev/packaging/tests/test_windows_msi_identity.py`.
- [x] `S08` - Author separate immutable version and shared registration WiX products for both scopes, with combined manager MSI refused until native maintenance is integrated; `dev/packaging/native/windows_msi.py, dev/packaging/native/windows_msi_identity.py, native/cmake/distribution, dev/packaging/tests/test_windows_msi.py, dev/packaging/native/tests/test_distribution_prepare.py and native/CONTRACT.md`.
- [x] `S10` - Preserve native registry scope in discovery and enforce verified this-user fallback before newer machine installations; `native/platform/src/installation.rs, native/application installation catalogue and tests, native/manager/src/installation.rs, native/desktop/src-tauri manager consumers and tests, and native/CONTRACT.md`.
- [x] `S11` - Integrate scoped MSI compilation, database verification and fail-closed installation readiness into the CMake distribution graph; `native/cmake/distribution, dev/packaging/native Windows MSI build helpers and tests, native/CONTRACT.md`.
- [x] `S12` - Implement shared installer publication state, catalogue admission, anchor retention and version leases before native MSI adapter integration; `native/application installation maintenance and catalogue, manager and desktop lease consumers, native/package-layout.json and owning tests`.
- [ ] `S09` - Integrate native MSI transaction publication and scope admission with catalogue startup and removal exclusion; `native/application installation catalogue, native installer maintenance adapter and native/cmake/distribution`.
- [ ] `S03` - Implement native installation registration and ownership-aware uninstall; `native/cmake, native/desktop build identity, and dev/packaging/native installation helpers`.
- [ ] `S04` - Verify native install upgrade launch and uninstall across the supported matrix and review; `dev/packaging/tests and native package verification`.
- [x] `S13` - Enable and verify CMake native Linux component builds with the pinned manylinux toolchain and explicit payload configuration; `CMakeLists.txt, native/cmake/ManylinuxToolchain.cmake and native/CONTRACT.md with native Linux compile and platform test evidence`.
- [ ] `S05` - Centralize build output paths and generation ownership in CMake and remove unowned build clutter; `native/cmake, native/desktop, dev/packaging/native, dev/packaging/tests, dev/docs sequence build helpers and owning tests, and build`.
- [x] `S14` - Separate registered local filing settlement from the bounded exchange timeout exposed by frozen installer documentation acceptance; `src/cadrumo/entrypoints/cli/runtime_modelo_verification.py filing function only and new owning filing settlement tests, preserving independent verification changes`.

## Parallelization

Execute sequentially. Preserve independent application-core and desktop edits in the shared checkout.

2026-10-08: S09 native MSI maintenance may run alongside root-owned S05 Linux CMake build enrollment. The MSI worker owns a native installer adapter, its transaction/scope/removal tests, windows_msi.py authoring integration and installer-only CMake enrollment. Root owns Linux toolchain/container orchestration, distribution documentation, vault edits and commits. The separate manager worker owns manager IPC/tray/preferences; coordinate any shared native/application maintenance changes with root and serialize native Cargo verification. Preserve the installability gate until protections and acceptance pass.


2026-10-08 native macOS builder integration: after completing native component evidence, linux_manager may own a repository Darwin toolchain file, its focused admission checks and isolated verification on the actual Mac. Translate the working explicit compiler/SDK selection into reproducible CMake inputs without hardcoding the operator's home directory, changing the canonical target/deployment floor or inventing release signing. Preserve explicit Rust linker configuration and exact builder/SDK identity. Coordinate shared CMake enrollment with root; root owns full-package build sessions, documentation source edits, vault and commits.


2026-10-08 stable Windows build recovery: after the live-checkout full docs attempt failed with deadline/connection outcomes, msi_maintenance may prepare an isolated canonical Windows source snapshot and pinned builder, then run the four failing documentation pages against those fixed inputs. Preserve existing Windows host/product/services and all unrelated working-tree edits. Never copy dotenv/private credentials into the snapshot. Root owns any source fixes, shared build decisions and commits; a full frozen native-installer retry requires those focused pages to pass first and coordination with root. WSL and Mac frozen runs may continue independently.


Frozen Windows diagnostic follow-up: notice_review owns ignored payload-free timing instrumentation and one coordinated Renta page reproduction after msi_maintenance releases the focused four-page lane. Record operation definition, settlement time, remaining result budget and per-page latency/count; no production edits, deadline increases or golden changes. Root chooses any correction only after this evidence and coordinates with unrelated runtime/performance owners.


Timing follow-up scheduling correction: because the Modelo390 page contains eleven long scenarios, root authorizes one Renta diagnostic concurrently in its own diagnostic-storage and diagnostic-temp. Its evidence must record concurrent Windows Modelo390 and WSL docs activity; timings establish the observed code/budget path, not isolated performance causality. Sources, golden files and deadlines remain unchanged.


S14: linux_manager may own only the filing constant/signature/settlement forwarding in runtime_modelo_verification.py and a new test_runtime_modelo_filing_settlement.py under its owning CLI tests. Preserve the existing independent verification edits in that same module and the dirty existing error-detail tests; no broad refactor. Reuse the real registered protocol/clock test patterns with bounded policy tests. Root owns review, frozen source overlay after the current docs batch completes, native failed-sequence rerun, vault and scoped partial-hunk commit.


Post-S14 native diagnostic follow-up: notice_review owns an ignored one-scenario forensic harness under the frozen Windows evidence directory, using the existing execute_sequence sandbox_root parameter to retain synthetic files while preserving normal runtime/worker cleanup. Capture only failure type, traceback locations, bounded cleanup flags and process exit metadata through existing observation points; do not log messages/locals/payloads or alter native semantics. Root reviews before one targeted launch. msi_maintenance retains Windows/WSL build inputs and copies bounded failed-build diagnostics; no new full build or overlay without coordination.


## Verification

Identity tests cover every canonical target, stable upgrade identity, channel isolation, version constraints and metadata escaping. Configure and build checks exercise the available Windows toolchain. Linux package checks run where available. Native install, upgrade, launch and uninstall must pass on each claimed supported platform; definitions and simulated fixtures alone do not establish release support. Uninstall preserves modified files, unrelated files and user data. Signing and notarization remain explicit release prerequisites where credentials are unavailable.
