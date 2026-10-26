---
tags:
  - '#plan'
  - '#tui-startup'
date: '2026-10-15'
tier: L1
related:
  - '[[2026-10-13-startup-performance-operation-contract-manifest-adr]]'
  - '[[2026-09-02-unreachable-capability-tui-navigation-join-adr]]'
modified: '2026-10-15'
body_schema: body-v2
body_hash: 'sha256:e37ea47cdc5fcd2bdc08f9f0ec4ae53cc1a2d0800c3dfc758e8b43aed30bac25'
---

# `tui-startup` plan

## Description

Approved 2026-10-15. The owner requested "improve" after the startup audit and explanation that incomplete profiles should reach setup before loading the workbench. This authorizes S01 and the audited agent-startup correction S02.

S01 follows the accepted incomplete-profile startup amendment in 2026-09-02-unreachable-capability-tui-navigation-join-adr and the unchanged manifest decision 2026-10-13-startup-performance-operation-contract-manifest-adr. Same exact runtime client, guarded profile mutations and explicit completion remain authoritative. A profile-only initial binding defers full Home capture; it never invents an empty generation. Source evidence is 2026-10-15-startup-performance-desktop-tui-sequence-audit. S02 fixes a machine-observation mismatch using the existing opaque-identifier reveal option scoped to native identity reads; normal CLI output remains private. No new credential or admission authority is added.

## Steps

- [ ] `S01` - Defer full workbench composition until Home is requested for an authenticated incomplete profile; retain account lifecycle and add startup timings and regression coverage; `src/cadrumo/entrypoints/tui`.
- [ ] `S02` - Repair native agent profile identity observation without changing ordinary CLI redaction and verify the default-environment contract; `native/desktop/src-tauri/src/shell/sign_in`.
- [ ] `S03` - Reduce sequential wizard overview reads within existing byte and revision bounds; verify complete reconstruction; `src/cadrumo/application/user_profile`.

## Parallelization

Implementation is sequential and owned by the parent. Luna max agents gather context and summarize logs or test output only. Preserve concurrent profile-wizard, runtime and packaging edits; no shared source files are delegated for writes.

## Verification

S01: focused root/account/installed-session tests; real native incomplete-profile startup, Home-return and session retirement coverage; fresh-process import graph and before/after timings. Run configured Python style, format, type and import checks, then required repository gates with unrelated failures reported separately. S02: canonical JSON redaction reproduction, native command environment and wire regression tests through configured desktop CMake targets, Rust formatting and native lint. Final integrated review must cover refusal, exact-profile checks, cancellation, delayed Home and unchanged complete-profile behavior. No package-speed claim without measuring a rebuilt package; retain source measurements separately.
