---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S122'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W03.P11.S122 Live IVA Remote-State Verification

Scope: verify residual live package behavior and public facade imports after root decomposition.

## Description

- Verified Ruff and compileall on the live package root and new IVA remote-state module.
- Verified IVA remote-state acquisition, filed-history capture, IVA wallet capture backend, filed bulk capture, and CLI live read/notifications/portals lanes.
- Verified public live facade imports for IVA remote-state functions and legacy private compatibility aliases.
- Scanned entrypoint, adapter, and domain production code for direct private live submodule imports.

## Outcome

Live root decomposition preserves behavior and keeps production consumers on `aeat.application.live`. Remaining direct private live imports are test-only fixtures and existing test coverage surfaces.

## Notes

Verification passed: `ruff check`, `compileall`, 39 focused application live tests, and 36 focused CLI live tests. Marker policy deselected remote live-read tests from the local non-live run.
