---
tags:
  - '#plan'
  - '#desktop-startup'
date: '2026-10-07'
tier: L1
related:
  - '[[2026-10-04-desktop-shell-adr]]'
  - '[[2026-10-04-canonical-environment-adr]]'
  - '[[2026-10-03-application-packaging-interpreter-foundation-adr]]'
modified: '2026-10-07'
body_schema: body-v2
body_hash: 'sha256:ea469d6a59d6814ddc1b2a023b21a69573980db007062c05020331a37b922093'
---

# `desktop-startup` plan

## Description

Approved 2026-10-07

The user requested investigation of slow Tauri startup and blank external terminal windows, then instructed continuation after the findings and proposed fixes. Authorization covers implementation and verification of those startup corrections. Reuse the accepted shell, canonical environment and interpreter decisions; preserve CLI behavior, canonical Settings ownership, storage pins, authentication boundaries and terminal persistence. No new persisted product schema or runtime authority is introduced.

Observed session 1 host 81268 spends 3587 ms in the Python environment child before GUI setup. The shipped PE subsystem is console. Console and Python panes start even when hidden. Account reads use fresh CLI children under the accepted sign-in boundary.

## Steps

- [x] `S01` - Start optional console and Python panes only on first visibility and retain their sessions thereafter; `native/desktop/frontend/src/components/TerminalPane.tsx, native/desktop/frontend/tests`.
- [x] `S02` - Remove blank launch consoles and reduce blocking startup preparation while preserving canonical configuration and headless behavior; `native/desktop/src-tauri, native/platform/src/desktop.rs, native/desktop/tests, scoped canonical projection dependencies as required`.
- [x] `S03` - Verify integrated startup behavior, record measured results and complete review; `native/desktop tests and startup audit`.

## Parallelization

S01 frontend terminal activation is delegated to a worker owning TerminalPane.tsx, layout.ts and its browser tests. Within S02 a second worker may own environment.rs, its Python query and narrowly scoped projection dependencies/tests, while the orchestrator owns main.rs, app.rs and native/platform/src/desktop.rs for console and startup ordering. These assignments may prepare concurrently with disjoint files. The orchestrator owns shared build outputs, plan updates, commits and integrated verification. Preserve all existing unrelated edits.

## Verification

Run frontend type, lint, format and focused browser behavior checks; native format, clippy, unit tests and applicable real packaged headless/projection checks. Verify no external shell is spawned until selected and hiding/reopening a used tab preserves its session. Verify Windows GUI-subsystem output preserves redirected headless output and error codes. Measure the fixed projection against the same staged interpreter; report session 1 GUI timing limitations explicitly. Review integrated work before completion.
