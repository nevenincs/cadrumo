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
modified: '2026-10-07'
body_schema: body-v2
body_hash: 'sha256:5469d42e74f9ea8508f925dfcb5fe55a0bb43c6449327739ceb056c367effd91'
---

# Application distribution

## Description

Approved 2026-10-04

The user explicitly requested implementation of product identity, modern CMake configuration, native installation and uninstall across Windows, Linux and macOS. The accepted application-distribution ADR governs identity and installer contracts. The interpreter-foundation and storage decisions continue governing runtime isolation. The accepted runtime-manager-architecture decision extends the earlier without-service-manager deferral with a per-user manager and scoped login registration; SCM services and scheduled tasks remain excluded. Existing application-core work owns native backend provisioning and Rust internals; actual cross-platform release proof depends on that work and suitable runners.

2026-10-07 authorization and recovery: the operator requested resolving the Google ADR validation error and completing installer/upgrade acceptance, then directed continued work. The Google error is repaired separately. Current Windows source/template review demonstrates that the combined MSI's major-upgrade policy violates preservation of prior in-use versions, and only perMachine is authored; S03 is reopened by this high finding. S04 remains open. The concrete proposed format decision is 2026-10-07-application-distribution-windows-versioned-msi-adr. It is an external unmet decision prerequisite, not governing accepted authority for this plan, and dependent source execution waits for its acceptance. The proposal is presented with the required source/host evidence in 2026-10-04-application-distribution-audit. After acceptance, refine S03 into cohesive identity, product authoring, transaction/scope admission and safe maintenance Steps using the owning plan verbs.

Live Windows acceptance also depends on manager-owned IPC, scoped default login start and opt-out, designated-successor cutover/rollback and uninstall detection in runtime-manager-architecture P02.S12-S13, P03.S14 and P04.S16-S17. Current source discovery does not complete those Steps. A disposable interactive Windows runner and two genuine distinct release payloads are required; development hosts receive no MSI, login registration or session-ending acceptance. Other target native backends, format decisions and signing remain explicit gates rather than covered by the Windows proposal.

## Steps

- [x] `S01` - Generate canonical product publisher channel and platform identities for all supported targets; `src/cadrumo/core/product_identity.py and dev/packaging/native/identity.py`.
- [x] `S02` - Project canonical identity into CMake project and platform packaging configuration; `CMakeLists.txt and native/cmake`.
- [ ] `S03` - Implement native installation registration and ownership-aware uninstall; `native/cmake, native/desktop build identity, and dev/packaging/native installation helpers`.
- [ ] `S04` - Verify native install upgrade launch and uninstall across the supported matrix and review; `dev/packaging/tests and native package verification`.
- [ ] `S05` - Centralize build output paths and generation ownership in CMake and remove unowned build clutter; `native/cmake, native/desktop, dev/packaging/native, dev/packaging/tests, and build`.

## Parallelization

Execute sequentially. Preserve independent application-core and desktop edits in the shared checkout.

## Verification

Identity tests cover every canonical target, stable upgrade identity, channel isolation, version constraints and metadata escaping. Configure and build checks exercise the available Windows toolchain. Linux package checks run where available. Native install, upgrade, launch and uninstall must pass on each claimed supported platform; definitions and simulated fixtures alone do not establish release support. Uninstall preserves modified files, unrelated files and user data. Signing and notarization remain explicit release prerequisites where credentials are unavailable.
