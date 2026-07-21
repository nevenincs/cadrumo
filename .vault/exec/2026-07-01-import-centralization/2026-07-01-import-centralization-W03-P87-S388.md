---
tags:
  - '#exec'
  - '#import-centralization'
date: '2026-07-02'
modified: '2026-07-17'
step_id: 'S388'
related:
  - "[[2026-07-01-import-centralization-plan]]"
---

# Exclude __main__.py modules from the shim/pure-reexport classifier in the import-hygiene scanner, since a module whose only statement is from .cli import app plus an if __name__ == "__main__": app() guard is the standard entrypoint pattern, not a Family-2 shim

## Scope

- `dev/import_hygiene_scan.py`
- `dev/tests/test_import_hygiene_scan.py`

## Description

- Excluded `__main__.py` modules from `find_shim_modules`'s pure-reexport classifier: the standard `from .cli import app` plus `if __name__ == "__main__": app()` entrypoint shape was false-positiving as a Family-2 shim (`src/aeat/locales/__main__.py`).
- Added two real-behavior regression tests against the live tree: one confirming `locales/__main__.py` is no longer flagged, one confirming a genuine pure-reexport module (`entrypoints/cli/_schemas.py`) is still flagged, guarding against an over-broad exclusion.
- Confirmed via a fresh scanner run that `locales/__main__.py` no longer appears under the Family-2 findings.

## Outcome

Committed alongside S364, S368, and S369 in one commit (`b6aafa707`). `dev/tests/test_import_hygiene_scan.py` (7 tests) green; `pytest --collect-only -q src/aeat` clean.

## Notes

None.
