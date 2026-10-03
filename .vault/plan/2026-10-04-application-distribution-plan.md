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
modified: '2026-10-03'
body_schema: body-v2
body_hash: 'sha256:dabb19baa98bdc1e6bea72a9b4358b24490f31c3865ce56685b2fc426495c033'
---

# Application distribution

## Description

Approved 2026-10-04

The user explicitly requested implementation of product identity, modern CMake configuration, native installation and uninstall across Windows, Linux and macOS. The application-distribution ADR governs identity and installer contracts. The interpreter-foundation and storage decisions continue governing runtime isolation. The runtime-without-service-manager decision excludes background service registration. Existing application-core work owns native backend provisioning and Rust internals; actual cross-platform release proof depends on that work and suitable runners.

## Steps

- [x] `S01` - Generate canonical product publisher channel and platform identities for all supported targets; `src/cadrumo/core/product_identity.py and dev/packaging/native/identity.py`.
- [x] `S02` - Project canonical identity into CMake project and platform packaging configuration; `CMakeLists.txt and native/cmake`.
- [x] `S03` - Implement native installation registration and ownership-aware uninstall; `native/cmake, native/desktop build identity, and dev/packaging/native installation helpers`.
- [ ] `S04` - Verify native install upgrade launch and uninstall across the supported matrix and review; `dev/packaging/tests and native package verification`.

## Parallelization

Execute sequentially. Preserve independent application-core and desktop edits in the shared checkout.

## Verification

Identity tests cover every canonical target, stable upgrade identity, channel isolation, version constraints and metadata escaping. Configure and build checks exercise the available Windows toolchain. Linux package checks run where available. Native install, upgrade, launch and uninstall must pass on each claimed supported platform; definitions and simulated fixtures alone do not establish release support. Uninstall preserves modified files, unrelated files and user data. Signing and notarization remain explicit release prerequisites where credentials are unavailable.
