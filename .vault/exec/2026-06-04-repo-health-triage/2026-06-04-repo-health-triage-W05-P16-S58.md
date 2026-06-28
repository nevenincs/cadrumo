---
tags:
  - '#exec'
  - '#repo-health-triage'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S58'
related:
  - '[[2026-06-04-repo-health-triage-plan]]'
---

# W05.P16.S58 - remove parsing private compatibility aliases

Scope: Wave `W05`; Phase `W05.P16`; Step `S58`.

## Description

- Removed underscore-prefixed parser aliases from the `aeat.core.parsing` package initializer.
- Kept public parser functions available through `parse_bool`, `parse_date`, `parse_iso8601_date`, and `parse_ddmmyyyy_date`.
- Added a public-surface regression test for the package initializer.
- Replaced the M036 CLI's direct `date.fromisoformat()` call with the public ISO parser after the parsing inventory gate exposed the bypass.

## Outcome

The S58 compatibility-alias surface is closed. Cross-package callers can no longer import the old private parser names from `aeat.core.parsing`, while implementation modules keep their private helpers for package-local tests and tightly scoped internal consumers.

## Notes

Verification:

- `uv run --no-sync ruff check src/aeat/core/parsing/__init__.py src/aeat/core/parsing/test_public_surface.py src/aeat/entrypoints/cli/_modelo_m036_cli.py`
- `uv run --no-sync pytest src/aeat/core/parsing/test_dates.py src/aeat/core/parsing/test_utils.py src/aeat/core/parsing/test_public_surface.py src/aeat/test_parsing_enrollment_inventory.py -q`
- `uv run --no-sync python -c "import aeat.core.parsing as p; print(p.__all__); print(hasattr(p, '_parse_iso8601_date'), hasattr(p, '_parse_bool'))"`

Broader CLI verification with `uv run --no-sync pytest src/aeat/entrypoints/cli/test_modelo.py src/aeat/entrypoints/cli/test_cli_surface.py -q` still has two residual failures outside S58: a source-inspection assertion for `work_calculate` after modelo CLI decomposition, and a ledger update fixture rejected by the taxable-base plus IVA invariant.
