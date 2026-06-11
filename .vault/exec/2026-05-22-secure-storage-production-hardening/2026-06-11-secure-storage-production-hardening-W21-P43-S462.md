---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-11'
step_id: 'S462'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# W21.P43.S462 CLI Startup Registration Repair

Scope: `src/aeat/entrypoints/cli`, `src/aeat/application/wizard`, `src/aeat/core/wizard_catalogue`, and `src/aeat/entrypoints/cli/tests`.

## Description

- Added W21/P43/S462 to track the CLI verification blocker exposed by S454.
- Root-caused the modelo CLI failure to `_activate_active_bucket_session()` returning early when an active bucket session was already open.
- Moved wizard catalogue/project-answer registration before the already-open-session return.
- Updated the cold-process wizard registration guard to supply the file secret-store backend and passphrase through the centralized `Settings` env contract.
- Reran the previously failing modelo CLI casilla-normalisation coverage and the cold-process registration guard.

## Outcome

S462 is complete. CLI startup now registers the wizard catalogue both when the root callback opens the bucket session and when a real test/runtime has already opened the active bucket session.

## Notes

The S462 repair did not change wizard catalogue ownership or domain imports. It only makes the existing composition-root registration hook run before both active-session exit paths.
