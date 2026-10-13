---
tags:
  - '#audit'
  - '#native-agent'
date: '2026-10-13'
modified: '2026-10-13'
body_schema: 'body-v2'
body_hash: 'sha256:9e4bb54dc3c460451af3ddec4e6beea9fa533299859942371cce54fc7c2a077b'
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

The owner clarified that CMake must accept a configurable local agent project folder, with no source SHA pin or download. Compatible dependency locks remain required, and the installed agent must be verified using the assembled application's interpreter. Runtime consumers must never fetch, install, build or add a source checkout to import paths. Source-only unit checks can diagnose build tooling; they do not establish installed-product acceptance.
