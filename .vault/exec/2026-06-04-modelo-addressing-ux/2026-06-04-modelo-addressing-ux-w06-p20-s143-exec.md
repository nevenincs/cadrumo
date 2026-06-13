---
tags:
  - '#exec'
  - '#modelo-addressing-ux'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S143'
related:
  - '[[2026-06-04-modelo-addressing-ux-plan]]'
---

# W06.P20.S143 Modelo CLI architecture guard

Scope:
- `src/aeat/entrypoints/cli/test_architecture_boundaries.py`

## Description

- Add static tests over extracted `_modelo*.py` CLI modules.
- Refuse extracted modules importing the legacy `_modelo.py` root.
- Refuse private application-module imports from extracted modelo CLI modules.
- Refuse untracked private domain imports, with the current exception-boundary rows named explicitly.

## Outcome

- Future command-group modules cannot rebuild hidden dependencies on the monolithic root.
- Future CLI modules cannot bypass application facades without a visible test failure.
- Existing exception-specific private domain imports are explicit debt rows instead of silent drift.

## Notes

- The guard is progressive for extracted modelo modules. The legacy `_modelo.py` root remains excluded until its command groups are fully split.

Verification:
- `.venv\Scripts\pytest.exe src/aeat/entrypoints/cli/test_architecture_boundaries.py -q` - passed as part of the 25-test focused gate.
