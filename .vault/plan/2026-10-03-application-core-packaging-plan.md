---
tags:
  - '#plan'
  - '#application-core-packaging'
date: '2026-10-03'
tier: L1
related:
  - '[[2026-10-03-application-packaging-interpreter-foundation-adr]]'
  - '[[2026-10-03-application-packaging-adr]]'
  - '[[2026-09-02-python-runtime-compatibility-adr]]'
  - '[[2026-06-28-product-packaging-adr]]'
  - '[[2026-08-03-canonical-storage-management-adr]]'
  - '[[2026-09-20-lud-authority-adr]]'
  - '[[2026-10-03-runtime-without-service-manager-adr]]'
modified: '2026-10-03'
body_schema: body-v2
body_hash: 'sha256:ca335164d049fea4ade0e84144a993e59189a4f73c4fc9b7cf2f3153eee0edde'
---

# `application-core-packaging` plan

## Description

Draft continuation requested 2026-10-03. The user explicitly requires a multiplatform build framework: Windows x64, Linux x64, Linux ARM64 and macOS ARM64. Windows is the current development host, not the framework's architecture. Shared policy and build stages must be portable; OS APIs, loaders, compiler settings and resource formats belong in bounded target adapters. Tauri remains settled.

This plan follows `2026-10-03-application-packaging-plan`; it does not take over or close that session's open Steps. The requested deliverable here is the continuation plan, not execution of its new management capabilities. S01 records the stable handoff before shared files change. Earlier macOS deferral bounded the Windows interpreter proof; it does not defer this plan's required macOS build conformance. Full application runtime platform behavior and the Tauri UI remain separately owned.

Decision coverage: `2026-10-03-application-packaging-interpreter-foundation-adr` governs retained interpreter/ABI ownership; `2026-09-02-python-runtime-compatibility-adr` and `2026-06-28-product-packaging-adr` govern the pin, dependency closure and exact-version cohort in S02-S05/S10-S11. `2026-08-03-canonical-storage-management-adr` and `2026-09-20-lud-authority-adr` govern generated paths, custody and published authority in S01/S07-S09. `2026-10-03-runtime-without-service-manager-adr` excludes service installation, autostart and runtime supervision throughout. The proposed `2026-10-03-application-packaging-adr` supplies S06-S10's application-library composition; S01 must reconcile its affected clauses and obtain decision coverage before dependent implementation. This draft does not promote the whole proposal.

### Current evidence and required corrections

Read on 2026-10-03 while the interpreter session was editing these files:

- `native/CONTRACT.md` now defines CMake outputs under `build/`; prior `.artifacts/native/` proofs are historical, not evidence for the revised ZIP package.
- The current Windows payload uses `python.zip`, `cadrumo/site-packages/`, controlled `cadrumo/python.pth`, native modules under `bin/`, and `data/package-manifest.json`. Consume the layout projection, not the older `python/Lib/` sketch.
- `CMakeLists.txt:11` and its MSVC checks restrict the shared graph to Windows. `native/toolchain.json` mixes common pins with one target's compiler/SDK details.
- `dev/packaging/native/layout.py:16` defaults to the build host; `assemble.py:35` evaluates dependency markers against that host. Provisioning/product helpers execute the selected SDK interpreter. These must not silently determine a different target's package.
- `stdlib.py:19` requires the exact pinned build-host Python for bytecode generation. Preserve that requirement and prove target bytecode/ABI compatibility explicitly.
- The storage policy in the accepted foundation ADR differs from the current Settings-projected developer behavior documented in `native/CONTRACT.md`. S01 resolves delivered-user defaults, allowed overrides and containment through the storage owner; neither the continuation nor a second Rust parser silently chooses a new root.
- Existing `build/windows-x64/artifacts-Release.json` is a generated output locator. Its existence does not prove current-source package validity.

### Canonical targets

Reuse `dev/packaging/runtime_wheelhouse_contract.py:52` as the existing target/marker/floor owner. Extend or project that authority; do not maintain a second target list in Rust, CMake or CI.

| Required target | Existing canonical identity | Current declared floor |
| --- | --- | --- |
| Windows x64 | `windows-x86-64` | Windows 10 |
| Linux x64 | `linux-x86-64` | glibc 2.28 |
| Linux ARM64 | `linux-aarch64` | glibc 2.28 |
| macOS ARM64 | `macos-arm64` | macOS 14.0 |

These are current repository declarations, not newly verified support claims. Reconcile the native `windows-x64` spelling through one generated mapping or coordinated rename. Carry target identity, architecture, ABI, deployment floor and SDK provenance into metadata and cache keys. Host/target combinations need explicit toolchain admission: four supported targets do not imply arbitrary cross-compilation from Windows. Required rows cannot disappear because a runner or wheel is unavailable.

### Source and output ownership

| Owner | Responsibility |
| --- | --- |
| `CMakeLists.txt`, `CMakePresets.json`, `native/cmake/` | One configure/build/test/install/package/clean graph; target adapters select native details. |
| `native/interpreter/`, `native/platform/` | Existing bootstrap, loader and platform-policy owners; retain the versioned C ABI and selected static bootstrap linkage. |
| `dev/packaging/native/` | Build-host operations and generated projections; reuse `python_cohort.py`, wheelhouse contracts and lock exporters in `dev/packaging/`. Never ship or import these helpers at application runtime. |
| `native/package-layout.json`, target mappings | Shared logical locations plus physical mappings; Settings/taxonomy remain the storage authority. |
| `native/application/` (new) | Portable Rust application-management library, depending on the platform owner and consuming generated contracts. No GUI dependency. |
| `native/components.json`, `dev/packaging/native/components.py` (new) | Author only missing capability/download metadata. Project existing versions, target identities and Python dependency facts; extend the assembled manifest without a second file inventory. |

Let `B` be the selected CMake binary directory, conventionally `build/<canonical-target>/`. Honor an explicit binary directory. Preserve the existing artifact roles:

```text
B/
  _deps/runtime/                 target SDK and dependency staging
  _deps/build-tools/             host-executed build tools
  product/build/wheels/          canonical Python cohort inputs
  product/dependencies/          selected target closure
  generated/                    contracts and build identity
  bin/<Config>/, lib/<Config>/, symbols/<Config>/
  cargo/                         target-separated Rust outputs
  stage/<Config>/app/             complete delivered tree
  packages/<Config>/             archives
  artifacts-<Config>.json         generated artifact locator
  testing/<Config>/, verification/<Config>/
  install/                       default local installation prefix
```

`build/` is disposable output, not a source package or application user-data root. Reuse across Debug/Release requires identical relevant ABI/input identity; no target may reuse another target's binaries. Cleanup remains bounded to declared generated children and preserves source, installed applications, other targets and user data. Shared logical layout does not require identical Windows, Linux-prefix and macOS-bundle directory trees.

### Scope of the next application segment

Deliver typed package inventory/readiness, immutable child-process configuration and one explicit Chromium provisioning flow. The application library owns download verification, staging and activation; existing Python services retain browser behavior, authorization, encrypted storage and model-admission policy. Package inspection performs no network access or provisioning.

The component contract must represent optional Python dependencies, Google client-library/public-registration requirements, local-model engines/weights and authority retention without claiming they are implemented. Their full provisioning flows, the Tauri shell, installers, public signing/publication, independent authority updates and runtime supervision are follow-on work. Chromium remains downloadable. Settle trusted download metadata, delivered storage policy and contract compatibility in S01; do not turn plain package hashes into a signature claim.

## Steps

- [ ] `S01` - Record the interpreter handoff and reconcile delivered storage, manifest and target contracts against current source; settle dependent decision wording before implementation; `.vault/adr/2026-10-03-application-packaging-adr.md, native/CONTRACT.md and this plan`.
- [ ] `S02` - Make CMake configuration, build stages and output paths target-driven across all four canonical targets; isolate compiler and resource differences in adapters; `CMakeLists.txt, CMakePresets.json, native/cmake/, native/toolchain.json, native/platforms/ and dev/packaging/native/layout.py`.
- [ ] `S03` - Pass an explicit target through SDK acquisition, wheel selection, contract generation, metadata, bytecode assembly and reuse keys without executing a foreign target interpreter; `dev/packaging/native/, native/package-layout.json and existing runtime_wheelhouse_contract.py consumers`.
- [ ] `S04` - Implement shared Linux native host, loader and packaging adapters for both x86-64 and AArch64 and prove real dependency imports; `native/interpreter/linux/, native/platform/src/ platform adapters, native/cmake/ and dev/packaging/native/platforms/ (Linux additions)`.
- [ ] `S05` - Implement macOS ARM64 native host, loader and bundle mappings with deployment-floor and signing compatibility proof; `native/interpreter/macos/, native/platform/src/ platform adapters, native/cmake/ and dev/packaging/native/platforms/ (macOS additions)`.
- [ ] `S06` - Create the portable Rust application library and typed component/readiness contracts, extending the existing assembled manifest through one generator; `native/application/ (new), native/components.json (new) and dev/packaging/native/components.py (new)`.
- [ ] `S07` - Expose immutable child-process environment and configuration projections through the platform boundary, preserving canonical Settings and storage ownership; `native/platform/, native/application/ and dev/packaging/native/generate.py`.
- [ ] `S08` - Implement verified component staging and activation with bounded extraction, target-aware selection, cancellation, writer exclusion and interruption recovery; `native/application/ component store and owning tests`.
- [ ] `S09` - Integrate explicit Chromium provisioning and capability inspection for each target while preserving Python browser ownership and declared user-data containment; `native/application/ browser adapter, native/components.json and existing Python browser/provisioning interfaces`.
- [ ] `S10` - Assemble the application library and capability metadata through the common CMake graph and existing package manifest without copying development tooling into delivery; `native/application/CMakeLists.txt (new), native/cmake/Packaging.cmake and dev/packaging/native/assemble.py`.
- [ ] `S11` - Prove build, package, relocation, component lifecycle and cleanup on all four targets and complete integrated review with artifact-bound evidence; `native/tests/, dev/packaging/native/ verification helpers and application-core-packaging audit`.

## Parallelization

The existing interpreter session retains exclusive ownership of its current `native/`, `dev/packaging/native/`, root CMake files and acceptance outputs until the S01 handoff. Re-read its final contract and reconcile the shared-file diff before integrating; do not overwrite concurrent changes or reuse historical green evidence.

S01 precedes execution. S02 then S03 establish the common target contract. S04 and S05 use separate platform adapters but share one integrator for CMake and declarations. After S01 fixes the interface, S06's new library and component-schema work may proceed alongside S02-S05 with disjoint ownership; changes to shared generators wait for the foundation owner. S07 follows S02-S06, then S08 and S09. S10 joins those results; S11 closes the complete four-target proof.

Each executor uses its own CMake binary directory. Builds, cleanup and verification never race in a shared `B`. No parallel worker may edit the canonical target list or shared manifests independently.

## Verification

- S01 produces one current-source handoff with resolved decision coverage and explicit remaining limits. It does not mark the predecessor's open Steps complete.
- Run the same build-stage contract for all four canonical targets. Inspect generated projections on the development host, then compile and run the delivered artifact on each matching OS/architecture. Missing toolchains, runners or dependencies leave the relevant Step open; a preset or cross-compiled file alone is insufficient.
- Verify explicit target propagation through marker evaluation, wheel tags, CPython SDK, native compiler/Cargo target, bytecode, metadata and cache keys. A deliberately mismatched host/target or wrong-architecture dependency must be rejected without contaminating another target's output.
- Prove Debug/Release separation, optional development-host policy, clean rebuild, valid reuse and invalidation after changed target/toolchain/lock/layout inputs. Inspect ZIP extraction for executable permissions, native-library identities and relocation on Linux/macOS as well as Windows.
- Consume one exact-version Python cohort per acceptance campaign. New application bytes enter the existing manifest before final hashing; `--check-package` continues to detect mixed, damaged and unexpected contents. Verify a relocated artifact outside the checkout, including spaces/Unicode, pure/native imports, child interpreter identity and read-only installation behavior.
- The application library's inspection API returns typed ready/missing/incompatible/needs-user states without effects. Child environment construction must not mutate global process environment after Tauri or other host threads start. Package and storage paths come from generated contracts and owning APIs.
- Exercise component acquisition against actual bounded archives/filesystem operations: wrong digest/target, traversal and links, interrupted extraction, cancellation, concurrent writers and failed activation preserve the prior active component. Verify explicit Chromium acquisition and Python browser compatibility for each target; missing upstream artifacts remain named blockers.
- Trace writes for the new provisioning/child workflow on each OS with appropriate tooling. Prove the agreed user-root containment and secure-custody boundary; the old Windows interpreter trace does not cover these workflows. No real taxpayer data, Google credentials or OS service registration is needed.
- Run focused Rust, C/CMake and Python checks using their configured owners, then one integrated review of exact artifacts and source revision. Keep build, runtime, packaging and broader application support claims distinct. Run Vaultspec record and plan checks before handover.
