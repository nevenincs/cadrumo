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
body_hash: 'sha256:9ff42846d4ab9241e7989451ed94717e2574e137d5d3d016e168781c7fcd1a7b'
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

## Steps

- [x] `S01` - Generate canonical product publisher channel and platform identities for all supported targets; `src/cadrumo/core/product_identity.py and dev/packaging/native/identity.py`.
- [x] `S02` - Project canonical identity into CMake project and platform packaging configuration; `CMakeLists.txt and native/cmake`.
- [x] `S06` - Expose native MSI, DMG and DEB/RPM delivery targets and presets with archives as explicit auxiliary outputs; `native/cmake/distribution, dev/packaging/native/tests/test_distribution_prepare.py and native/CONTRACT.md`.
- [x] `S07` - Separate Windows MSI product and component identities by ownership role, installation scope and release without changing legacy identities; `dev/packaging/native/identity.py, dev/packaging/native/windows_msi_identity.py and dev/packaging/tests/test_windows_msi_identity.py`.
- [x] `S08` - Author separate immutable version and shared registration WiX products for both scopes, with combined manager MSI refused until native maintenance is integrated; `dev/packaging/native/windows_msi.py, dev/packaging/native/windows_msi_identity.py, native/cmake/distribution, dev/packaging/tests/test_windows_msi.py, dev/packaging/native/tests/test_distribution_prepare.py and native/CONTRACT.md`.
- [x] `S10` - Preserve native registry scope in discovery and enforce verified this-user fallback before newer machine installations; `native/platform/src/installation.rs, native/application installation catalogue and tests, native/manager/src/installation.rs, native/desktop/src-tauri manager consumers and tests, and native/CONTRACT.md`.
- [x] `S11` - Integrate scoped MSI compilation, database verification and fail-closed installation readiness into the CMake distribution graph; `native/cmake/distribution, dev/packaging/native Windows MSI build helpers and tests, native/CONTRACT.md`.
- [ ] `S09` - Integrate native MSI transaction publication and scope admission with catalogue startup and removal exclusion; `native/application installation catalogue, native installer maintenance adapter and native/cmake/distribution`.
- [ ] `S03` - Implement native installation registration and ownership-aware uninstall; `native/cmake, native/desktop build identity, and dev/packaging/native installation helpers`.
- [ ] `S04` - Verify native install upgrade launch and uninstall across the supported matrix and review; `dev/packaging/tests and native package verification`.
- [ ] `S05` - Centralize build output paths and generation ownership in CMake and remove unowned build clutter; `native/cmake, native/desktop, dev/packaging/native, dev/packaging/tests, and build`.

## Parallelization

Execute sequentially. Preserve independent application-core and desktop edits in the shared checkout.

## Verification

Identity tests cover every canonical target, stable upgrade identity, channel isolation, version constraints and metadata escaping. Configure and build checks exercise the available Windows toolchain. Linux package checks run where available. Native install, upgrade, launch and uninstall must pass on each claimed supported platform; definitions and simulated fixtures alone do not establish release support. Uninstall preserves modified files, unrelated files and user data. Signing and notarization remain explicit release prerequisites where credentials are unavailable.
