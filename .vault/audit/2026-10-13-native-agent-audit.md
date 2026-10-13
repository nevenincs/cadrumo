---
tags:
  - '#audit'
  - '#native-agent'
date: '2026-10-13'
modified: '2026-10-13'
body_schema: 'body-v2'
body_hash: 'sha256:1ccf33f2c89b25d3d1ab007d90b12c6a64c9e7884c48854ed35356459a271d12'
related: []
---

# `native-agent` audit: `Native agent dependency ownership`

## Scope

Native CMake acquisition, wheel construction, dependency installation, staged-package verification and agent launch provenance. Static inspection preceded implementation; acceptance remains pending until the assembled package is exercised.

## Findings

### native-agent-missing-owner | high | Native builds do not provision the private agent

Initial inspection of `native/CMakeLists.txt` and `native/cmake/Packaging.cmake` found targets for CPython, the locked registry closure and Cadrumo product wheels, but no private agent source or wheel producer. `native/package-layout.json:14` declares the canonical custom package location. The agent repository is private and has no public index release.

### source-agent-launch | high | Desktop agent launches depend on an external source checkout

Initial `native/desktop/src-tauri/src/agent/mod.rs:34` consumed `CADRUMO_DESKTOP_AGENT_SOURCE` and passed `--agent-source` to the launcher. The proposed live-lane decision used that topology. The owner's 2026-10-13 instruction instead requires only CMake acquisition and build, and agent tests against the already-built custom app environment.

### repeated-source-globs | medium | Configure repeats the same source glob while its contents can change

Two real CMake configure attempts refused the duplicated `src/*` glob in `native/cmake/PackageInputs.cmake` and `native/cmake/Docs.cmake` because files were added between consumers. Sharing one configure inventory removes that inconsistency; a focused CMake fixture checks that late files appear at the following configure.

## Recommendations

The native-agent decision must bind private source acquisition to CMake, retain an immutable source pin and hash-pinned compatible dependency locks, and verify the installed agent using the assembled application's interpreter. Runtime consumers must never fetch, install, build or add a source checkout to import paths. Source-only unit checks can diagnose build tooling; they do not establish installed-product acceptance.
