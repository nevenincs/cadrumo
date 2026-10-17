---
tags:
  - '#plan'
  - '#windows-package-identity'
date: '2026-10-16'
tier: L1
related:
  - '[[2026-10-16-application-distribution-windows-package-identity-adr]]'
  - '[[2026-10-07-application-distribution-windows-versioned-msi-adr]]'
  - '[[2026-10-16-native-build-incremental-adr]]'
modified: '2026-10-17'
body_schema: body-v2
body_hash: 'sha256:35f2a0c521c23ff7b00a5d4eae64a281979f2701675b737407779a01905ec406'
---

# `windows-package-identity` plan

Register Cadrumo on Windows as one packaged application so every Cadrumo process groups under one Cadrumo entry.

## Description

Approved 2026-10-16. Basis: offered a package with external location registered by the installer, with a recommendation, the operator replied that it is critical that the application is registered.

Decision coverage: 2026-10-16-application-distribution-windows-package-identity-adr governs every Step; its evidence is 2026-10-16-application-distribution-windows-package-identity-research. 2026-10-07-application-distribution-windows-versioned-msi-adr, as amended by 2026-10-16-native-build-incremental-adr, governs installation ownership for S07 and S08. S01 to S05 give every Cadrumo image the identity and let a developer register a built stage tree; S06 waits on the operator's certificate-source choice; S07 waits on the single-MSI port in the native-build-incremental plan; S08 needs a disposable host.

## Steps

- [x] `S01` - Project the package name, publishers, application id, display name and registration version from the distribution identity owner; `dev/packaging/native/identity.py`.
- [x] `S02` - Render an identity-bearing process manifest for the C hosts, manager and agent image, keep the installer plain, and check each linked image against its role; `native/interpreter/windows/host.manifest`.
- [x] `S03` - Embed Tauri's manifest content plus the identity element in the desktop image; `native/desktop/src-tauri/build.rs`.
- [x] `S04` - Render the package manifest and its logo assets from the projection; `dev/packaging/native/package_identity.py`.
- [ ] `S05` - Add the developer command that loosely registers and removes a built stage tree, and prove one Cadrumo entry on the real Debug application; `dev/packaging/native/package_identity.py`.
- [ ] `S06` - Sign the package with the operator-chosen certificate source; `dev/packaging/native/package_identity.py`.
- [ ] `S07` - Register and remove the package per scope in the native maintenance owner within the shared-registration feature; `native/installer`.
- [ ] `S08` - Accept per-user and per-machine registration, removal and grouping on a disposable host; `native/installer`.

## Parallelization

S01 precedes S02 to S05. S02 and S03 touch disjoint files and can run in parallel. S05 needs a rebuilt Debug stage, coordinated with the session that owns the Debug build. S07 starts only after the native-build-incremental plan's MSI port lands, because both change the native maintenance owner.


## Verification

- The real application shows one Cadrumo entry in Task Manager containing the desktop, runtime, manager, agent service, agent and bundled Python; any Microsoft WebView2 processes are reported as observed.
- Every Cadrumo image built for Windows carries the identity element for its channel and build kind; the installer and maintenance runner carry none; divergence checks reject a mismatched image in an isolated fixture.
- Profile storage, settings and runtime admission behave identically with and without registration.
- Developer registration and removal leave no package behind; CI and tests never register.
- Both installation scopes register and remove the package on a disposable host, and a refused registration leaves a committed installation intact.
