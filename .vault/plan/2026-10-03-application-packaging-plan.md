---
tags:
  - '#plan'
  - '#application-packaging'
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
body_hash: 'sha256:81b688db49147603ccc546c438765d53a85a3bebdb5ef27b73b1f426fd42323f'
---

# `application-packaging` plan

## Description

Approved 2026-10-03

The user explicitly requested contracts, a compiled C host, shared Rust policy, Windows tooling and delivered-artifact verification. This authorizes S01-S04 within that foundation. The packaging ADR stays proposed for unresolved application choices. Its scoped foundation commitments come directly from the user brief; linkage is an evidence-led implementation choice. Existing accepted Python compatibility, exact-version cohort, Settings/taxonomy ownership, authority provisioning and runtime boundaries continue to govern. No storage migration, core default rewrite, Tauri UI, service management or installers are included. The user clarified that existing local storage is to be ignored for this work.

S01 owns native/CONTRACT.md and the package-only declaration. S02 owns the C ABI proof and pinned build. S03 owns the host and package assembler. S04 owns relocated acceptance evidence and final integrated review. Build outputs now live beneath build/windows-x64 under S05; authored sources never contain generated binaries. The earlier .artifacts/native evidence remains historical.

## Steps

- [x] `S01` - Establish ownership, platform mappings and scoped decision coverage; `native/ and dev/packaging/native/`.
- [x] `S02` - Prove Windows toolchains and C ABI linkage with pinned CPython; `native/`.
- [x] `S03` - Build isolated host and assemble the locked Python product; `native/ and dev/packaging/native/`.
- [x] `S04` - Verify relocated artifact, hostile environments, child processes and filesystem writes; `dev/packaging/native/ and native/`.
- [x] `S05` - Control Debug Release builds installation and ZIP packaging through CMake and CPack; `CMakeLists.txt, CMakePresets.json, native/ and dev/packaging/native/`.

S05 also covers the user-authorized naming and cleanup contract, optional `_d` host, Python ZIP library, Windows identity resources, locked third-party wheels, CADRUMO wheel builds, package-cohesion checks and platform backend separation. Shared packaging must not embed Windows physical filenames. Installation, extracted ZIP and development-host checks remain required before completion.

## Parallelization

Steps are sequential. One executor owns all native and packaging changes, shared checks and commits. Concurrent unrelated work in the checkout is excluded.

## Verification

Compile with CPython 3.13.11 headers/import library/runtime, MSVC 14.44.35207, SDK 10.0.26100.0 and Rust 1.96.0 MSVC. Prove C static/DLL and Rust consumers. Assemble the locked base dependencies and exact-version product wheels. Verify qualified native imports, hostile Python/DLL environments, unrelated cwd, Unicode/spaces, child interpreters, missing/incompatible inputs and temporary/cache writes. Record actual filesystem tracing coverage. Run focused lint/format/type checks and integrated review. Linux and macOS remain mapping obligations. Missing evidence leaves the corresponding Step open.
