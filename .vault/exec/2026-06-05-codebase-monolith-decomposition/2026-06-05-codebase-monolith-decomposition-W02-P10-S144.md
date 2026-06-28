---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S144'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W02.P10.S144 Profile Censo Split

Scope: split residual profile censo command registration into focused transport helpers without moving censo policy into CLI.

## Description

- Moved censo lifecycle event enrollment out of the CLI and into `CensoSyncService`.
- Added the application factory `build_censo_sync_service` so CLI construction wires the real bucket event repository without knowing event internals.
- Updated `_profile_censo.py` to resolve the active profile, call the application service, handle typed refusals, and render payloads only.
- Added a real event-history assertion for censo refresh through the production service factory.

## Outcome

The censo CLI module no longer constructs bucket events or reaches into event-history persistence. Event enrollment is application-owned, and the CLI remains a Typer transport over the user-profile facade.

## Notes

Ruff passed for the changed censo modules. Application censo service tests passed with 17 real-behavior tests, and profile censo CLI tests passed with 11 real-behavior tests. The full focused config CLI lane passed with 57 tests.
