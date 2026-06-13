---
tags:
  - '#exec'
  - '#repo-health-triage'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S57'
related:
  - '[[2026-06-04-repo-health-triage-plan]]'
---

# W05.P16.S57 - canonicalize filing-status token and remove shim surface

Scope: Wave `W05`; Phase `W05.P16`; Step `S57`.

## Description

- Moved the canonical `FilingStatus` enum to the lightweight operator-surface model layer.
- Updated the operator-surface contract and live CLI to consume that canonical enum directly.
- Removed the token-only `_filing_status_token.py` shim and the overview-owned `_status.py` enum module.
- Removed the overview package re-export so `FilingStatus` has one application-owned home.

## Outcome

The S57 filing-status shim is closed. The LIVE command-family contract and `aeat app live filed` Typer group now share the same canonical enum without importing the heavy overview package or duplicating the raw `"filed"` token.

## Notes

Verification:

- `uv run --no-sync ruff check src/aeat/application/operator_surface/_models.py src/aeat/application/operator_surface/_contract.py src/aeat/application/operator_surface/__init__.py src/aeat/application/operator_surface/test_contract.py src/aeat/entrypoints/cli/_app_live.py src/aeat/application/overview/__init__.py`
- `uv run --no-sync pytest src/aeat/application/operator_surface/test_contract.py src/aeat/entrypoints/cli/test_root_help_shape.py::test_root_help_uses_curated_two_root_shape src/aeat/entrypoints/cli/test_root_help_shape.py::test_config_and_app_help_use_curated_subtree_shape src/aeat/entrypoints/cli/test_registry_cli.py::test_live_filed_capture_sources_cli_help_resolves_without_registry_alias src/aeat/entrypoints/cli/test_registry_cli.py::test_live_filed_capture_all_cli_help_resolves -q`
- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_registry_cli.py -q -k "filed and help"`
- `uv run --no-sync python -m compileall -q src/aeat/application/operator_surface src/aeat/entrypoints/cli/_app_live.py src/aeat/application/overview/__init__.py`

The shared worktree still has unrelated calendar-event WIP in `src/aeat/application/overview/__init__.py` and live-IVA watchdog WIP in `src/aeat/entrypoints/cli/_app_live.py`. The S57 commit stages only the filing-status relocation hunks for those files.
