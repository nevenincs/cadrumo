---
tags:
  - '#plan'
  - '#application-core-packaging'
date: '2026-10-03'
tier: L1
related:
  - '[[2026-10-03-application-packaging-interpreter-foundation-adr]]'
  - '[[2026-09-02-python-runtime-compatibility-adr]]'
  - '[[2026-06-28-product-packaging-adr]]'
  - '[[2026-08-03-canonical-storage-management-adr]]'
  - '[[2026-09-20-lud-authority-adr]]'
  - '[[2026-10-03-runtime-without-service-manager-adr]]'
modified: '2026-10-03'
body_schema: body-v2
body_hash: 'sha256:a07b4345fd973f7bd76f77b511d2e8b6c14d27bd0e1af1e3285cb259b7fc1111'
---

# `application-core-packaging` plan

## Description

Approved 2026-10-03

Authorization: the user instructed this session to read and execute this continuation plan, while the separate interpreter/package-basis session remains active and cannot be contacted. The user clarified that this session owns the Rust application library while the other session owns Python packaging. Shared integration waits for handoff; independent Rust library implementation proceeds immediately.

Continuation requested 2026-10-03. The user explicitly requires a multiplatform build framework: Windows x64, Linux x64, Linux ARM64 and macOS ARM64. Windows is the current development host, not the framework's architecture. Shared policy and build stages must be portable; OS APIs, loaders, compiler settings and resource formats belong in bounded target adapters. Tauri remains settled.

This plan follows `2026-10-03-application-packaging-plan`; it does not take over or close that session's open Steps. The original deliverable was this continuation plan; the user's subsequent execution instruction authorizes its scoped implementation. S01 records the stable handoff before shared files change. Earlier macOS deferral bounded the Windows interpreter proof; it does not defer this plan's required macOS build conformance. Full application runtime platform behavior and the Tauri UI remain separately owned.

Decision coverage: `2026-10-03-application-packaging-interpreter-foundation-adr` governs retained interpreter/ABI ownership; `2026-09-02-python-runtime-compatibility-adr` and `2026-06-28-product-packaging-adr` govern the pin, dependency closure and exact-version cohort in S02-S05/S10-S11. `2026-08-03-canonical-storage-management-adr` and `2026-09-20-lud-authority-adr` govern generated paths, custody and published authority in S01/S07-S09. `2026-10-03-runtime-without-service-manager-adr` excludes service installation, autostart and runtime supervision throughout. The proposed `2026-10-03-application-packaging-adr` supplies design context. The user's explicit Rust-library clarification authorizes the standalone S06 implementation and library-owned S07-S08 behavior against supplied contracts; S01 still reconciles broader composition and shared integration before S09-S10 adoption. This execution authorization does not promote unrelated choices in the broader proposal.

### Current evidence and required corrections

Read on 2026-10-03 while the interpreter session was editing these files:

- `native/CONTRACT.md` now defines CMake outputs under `build/`; prior `.artifacts/native/` proofs are historical, not evidence for the revised ZIP package.
- The current Windows payload uses `python.zip`, `cadrumo/site-packages/`, controlled `cadrumo/python.pth`, native modules under `bin/`, and `data/package-manifest.json`. Consume the layout projection, not the older `python/Lib/` sketch.
- `CMakeLists.txt:11` and its MSVC checks restrict the shared graph to Windows. `native/toolchain.json` mixes common pins with one target's compiler/SDK details.
- `dev/packaging/native/layout.py:16` defaults to the build host; `assemble.py:35` evaluates dependency markers against that host. Provisioning/product helpers execute the selected SDK interpreter. These must not silently determine a different target's package.
- `stdlib.py:19` requires the exact pinned build-host Python for bytecode generation. Preserve that requirement and prove target bytecode/ABI compatibility explicitly.
- The accepted foundation ADR's CMake/platform amendment now explicitly supersedes the earlier Known Folder and empty-override policy with Settings-owned defaults and storage overrides, matching `native/CONTRACT.md`. S01 must still reconcile the broader proposed application ADR's delivered-user defaults and containment claims through the storage owner; neither the continuation nor a second Rust parser silently chooses a new root.
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

### S01 execution checkpoint, 2026-10-03

Read-only handoff assessment found that the interpreter session has not yet delivered the stable prerequisite. Its plan has S01 checked and S02-S05 open. `native/CONTRACT.md` explicitly says revised ZIP verification is in progress and historical evidence belongs to the earlier artifact. Scoped Git inspection shows modified shared native/generator files, deleted predecessors and untracked root CMake files, platform adapters and tests. No shared implementation or acceptance output was changed by this continuation session.

Confirmed current inputs: ABI 1; standard library `python.zip`; packages `cadrumo/site-packages`; native files `bin`; one assembled `data/package-manifest.json`; canonical four-target declarations in `dev/packaging/runtime_wheelhouse_contract.py`. Root CMake still rejects non-Windows hosts and only the `windows-x64` native mapping is declared. These observations identify integration work; they are not a final handoff or build verification.

Resume S01 from the interpreter owner's final source/contract and artifact-bound acceptance evidence once ownership is released. Reconcile the shared-file diff, target spelling, Settings projection, manifest compatibility and trusted Chromium download metadata before dependent implementation. Do not resurrect the superseded Known Folder policy or treat the old macOS pikepdf-floor observation as a newly reproduced dependency failure: the canonical target already declares macOS 14.0.

The initial assessment incorrectly blocked independent Rust work. The user corrected that interpretation: S01 remains an integration checkpoint, while S06 and the library-owned portions of S07-S09 may proceed in native/application/ using explicit input contracts. Shared generators, native/platform/, root CMake and Python packaging remain untouched until integration. No current-source build, target execution, provisioning or containment claim follows from this checkpoint.

### Rust library execution checkpoint, 2026-10-03

The user corrected the initial ownership interpretation: independent Rust library work is authorized while Python packaging continues. `native/application/` now contains `cadrumo-application`, a GUI-independent Rust crate consuming supplied package manifests, target identities, storage roots and child environments. No Python, native/platform or root CMake source was changed by this work.

S06 owns the independently testable crate and typed inventory/readiness surface. Library portions of S07 and S08 include immutable child commands and a verified ZIP component store with HTTPS transport, writer exclusion, staged activation, cancellation, retained repair generations and process-termination recovery. Their shared platform/storage integration and full target acceptance remain open. Component hashes establish integrity, not publisher authentication; private store ownership is a prerequisite, not a same-user filesystem sandbox.

The read-only review found and corrected Unix backslash aliasing, transport metadata being confused with content identity, and inability to repair oversized damaged versions. Receipts now retain archive entry counts for consistent admission on reuse. Focused checks and current results are recorded in the execution ledger and audit. Outputs are isolated under `build/windows-x86-64/application-core/` and `build/linux-x86-64/application-core/`.

S09 still needs trusted Chromium metadata and a complete projected Playwright requirement set. The existing Python owner requires both Chromium and headless-shell revisions and completion markers; installing one executable does not satisfy that contract. S10 retains assembler/metadata/platform integration. Linux ARM64, macOS ARM64 and full packaged execution remain unverified; the Windows/Linux library checks do not close S11.

## Steps

- [ ] `S01` - Record the interpreter handoff and reconcile delivered storage, manifest and target contracts against current source; settle dependent decision wording before implementation; `.vault/adr/2026-10-03-application-packaging-adr.md, native/CONTRACT.md and this plan`.
- [ ] `S02` - Make CMake configuration, build stages and output paths target-driven across all four canonical targets; isolate compiler and resource differences in adapters; `CMakeLists.txt, CMakePresets.json, native/cmake/, native/toolchain.json, native/platforms/ and dev/packaging/native/layout.py`.
- [ ] `S03` - Pass an explicit target through SDK acquisition, wheel selection, contract generation, metadata, bytecode assembly and reuse keys without executing a foreign target interpreter; `dev/packaging/native/, native/package-layout.json and existing runtime_wheelhouse_contract.py consumers`.
- [ ] `S04` - Implement shared Linux native host, loader and packaging adapters for both x86-64 and AArch64 and prove real dependency imports; `native/interpreter/linux/, native/platform/src/ platform adapters, native/cmake/ and dev/packaging/native/platforms/ (Linux additions)`.
- [ ] `S05` - Implement macOS ARM64 native host, loader and bundle mappings with deployment-floor and signing compatibility proof; `native/interpreter/macos/, native/platform/src/ platform adapters, native/cmake/ and dev/packaging/native/platforms/ (macOS additions)`.
- [x] `S06` - Create the independently buildable Rust application library and typed package inventory and capability readiness contracts consuming the existing manifest; shared metadata generation joins at S10; `native/application/ (new)`.
- [ ] `S07` - Expose immutable child-process environment and configuration projections through the platform boundary, preserving canonical Settings and storage ownership; `native/platform/, native/application/ and dev/packaging/native/generate.py`.
- [ ] `S08` - Implement verified component staging and activation with bounded extraction, target-aware selection, cancellation, writer exclusion and interruption recovery; `native/application/ component store and owning tests`.
- [ ] `S09` - Integrate explicit Chromium provisioning and capability inspection for each target while preserving Python browser ownership and declared user-data containment; `native/application/ browser adapter, native/components.json and existing Python browser/provisioning interfaces`.
- [ ] `S10` - Integrate the Rust application library, canonical platform projections and generated capability metadata through the common CMake graph and existing package manifest without copying development tooling into delivery; `native/application/CMakeLists.txt (new), native/components.json (new), dev/packaging/native/components.py (new), native/cmake/Packaging.cmake and dev/packaging/native/assemble.py`.
- [ ] `S11` - Prove build, package, relocation, component lifecycle and cleanup on all four targets and complete integrated review with artifact-bound evidence; `native/tests/, dev/packaging/native/ verification helpers and application-core-packaging audit`.

## Parallelization

User clarification on 2026-10-03 assigns this session the Rust application library and the other session the Python package. S01 gates shared integration, not independent library development. This session owns new files under `native/application/`; the Python session retains its current `native/platform/`, interpreter, shared declarations, root CMake, generators and acceptance outputs.

Proceed with S06 and library-owned S07-S09 against explicit input contracts. Consume target identity, package inventory and resolved storage/environment projections; do not duplicate the canonical target list or reimplement Settings defaults. Reconcile those interfaces at S01/S10 before changing shared owners. S02-S05 and four-target integrated acceptance remain outstanding.

Use `build/windows-x86-64/application-core/` for this session's Rust build and test outputs. Other targets use equivalent target-specific roots. Builds, cleanup and verification never race in the Python owner's binary directory.

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
