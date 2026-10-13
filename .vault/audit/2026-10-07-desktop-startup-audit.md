---
tags:
  - '#audit'
  - '#desktop-startup'
date: '2026-10-07'
modified: '2026-10-13'
body_schema: 'body-v2'
body_hash: 'sha256:440a9c122363005c3a6bab50e97b932bd8e88cea9e9579e4e93b8fc57d8bc09a'
related:
  - "[[2026-10-07-desktop-startup-plan]]"
---

# `desktop-startup` audit: `Windows startup performance and console behavior`

## Scope

## Findings

## Recommendations

## Context

## Scope

Review of startup changes in the working tree: lazy optional terminals, Windows GUI subsystem with existing-parent console attachment, and native projection of canonical generated defaults with Python fallback for explicit member settings. Other concurrent manager, logging and sign-in changes are outside this patch. Independent reviewer verdict PASS after corrections.

## Findings

### generation-dependencies | medium | Resolved missing canonical logging input

Review found the new generated desktop_defaults.log_format dependency absent from native/CMakeLists.txt. Added src/cadrumo/core/logging.py to native_contract dependencies. Canonical generator tests pass.

### authority-wording | low | Resolved obsolete query-only description

Updated accepted desktop-shell implementation wording and native/CONTRACT.md to describe build-generated canonical defaults and the runtime fallback. No new Settings authority introduced.

### verification | low | Passing scoped checks with explicit visual limitation

Passed 26 production-assets desktop browser tests, TypeScript, scoped ESLint/Prettier, 167 desktop native unit tests, 39 platform tests, nine packaged environment tests, six generator tests, Rust formatting and native Clippy with warnings denied. Built Debug cadrumo.exe at build/desktop-windows-x64/cargo/desktop/debug/cadrumo.exe. headless.test.mjs verified PE GUI subsystem value 2 plus exact stdout/stderr/exit parity, Unicode arguments, hostile Python environment and no-desktop/invalid-mode guards against the installed interpreter. Native projection equals the full Python environment and settings, launches no Environment child, and explicit member overrides use canonical Python including invalid temporary-directory refusal. Matching-cohort contract generated using current generator and installed Python definitions because another workstream changed the source log format. Final measured native preparation 390.9929 ms versus Python query 1566.3107 ms. This is a component comparison, not click-to-paint latency. Session 1 visual behavior and updated installed package remain unverified; running application was not replaced.

### concurrent-work | low | Broad scenario run and checkpoint limitations

Broad browser run passed 201 of 208 tests; seven log-view scenarios failed while concurrent edits triggered development-server HMR. All 26 focused production desktop tests passed subsequently. Concurrent diagnostic compile errors were repaired minimally for integration checks; unrelated diffs remain owned by their workstreams. Another Git index.lock prevented checkpoint staging on repeated attempts; no lock was removed and no unrelated changes were staged.

## Recommendations

Launch a newly assembled matching-cohort package in session 1 to measure complete window startup and visually confirm the absence of a transient console. Existing saved layouts that explicitly open a terminal still activate that selected terminal; new layouts start with the optional panel closed.
