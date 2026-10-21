---
tags:
  - '#plan'
  - '#desktop-titlebar'
date: '2026-10-09'
tier: L1
related:
  - '[[2026-10-09-desktop-titlebar-adr]]'
  - '[[2026-10-04-desktop-shell-adr]]'
  - '[[2026-10-05-desktop-design-system-adr]]'
  - '[[2026-10-04-application-sign-in-adr]]'
modified: '2026-10-09'
body_schema: body-v2
body_hash: 'sha256:3058ddd3d5f6e9ffc6b6fcbd83c067e8823def59ab9e97cace9c9bd4b2c00060'
---

# `desktop-titlebar` plan

## Description

Approved 2026-10-09

The user approved the existing mockup and requested proper Tauri implementation, explicitly retiring the duplicate Configuration/Settings profile switcher. The desktop-titlebar decision bounds the new native window contract; the desktop-shell and design-system decisions govern host isolation, controls and tokens; application-sign-in governs coherent profile selection and canonical authentication. One cohesive revision integrates native behavior and the single account surface.

## Parallelization

Execute serially in this worktree. Preserve unrelated runtime lifecycle and frontend edits.

## Verification

Frontend type checking, lint and formatting pass. Focused scenario and product tests cover account location, signed-in and signed-out interactions, unreadable profile lists, refusals, focus, alignment, layout and window control transport. Rust formatting, clippy and focused tests verify token rejection, typed window actions, native state and close handling. Build the native Windows desktop and exercise its window controls where the desktop session permits it. Report unavailable platform execution separately. Final integrated review must pass.

## Steps

- [x] `S01` - Implement the approved Tauri header and retire Settings account controls, verifying native window operations and account workflows; `native/desktop/src-tauri and native/desktop/frontend source and focused tests, native/desktop/tests/packaged, canonical dev.locales keys as needed`.
