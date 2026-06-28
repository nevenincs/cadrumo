---
tags: ['#exec', '#codebase-monolith-decomposition']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S18'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W02.P03.S18 - config diagnostics extraction

Scope: `src/aeat/entrypoints/cli/_config/__init__.py` and `src/aeat/entrypoints/cli/_config/_auth_diagnostics.py`.

## Description

- Added focused `_config._auth_diagnostics` command module for `config auth diagnostics`.
- Moved the diagnostics Typer app and `list`, `show`, and `report` command functions out of the config root.
- Left business behavior in `application.auth`; the extracted module remains a CLI consumer that emits payload envelopes and translates boundary errors.
- Re-exported the mounted diagnostics Typer app through the config root import path by importing it in `src/aeat/entrypoints/cli/_config/__init__.py`.

## Outcome

Extraction completed. The config root now imports and mounts `auth_diagnostics_app` instead of defining the diagnostics command group inline.

## Notes

No raw command semantics were changed. The top-level config module remains the public façade for consumers that import mounted Typer apps.
