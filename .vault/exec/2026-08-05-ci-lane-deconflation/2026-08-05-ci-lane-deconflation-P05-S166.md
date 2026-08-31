---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:f090b63a2ae23a7326177d295af2657cf7deb5e1aea5e3ba6f56419ee491649d'
step_id: 'S166'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
# `ci-lane-deconflation` execution record: `P05.S166`

## Scope

- `P05.S166`

## Changes

- `M` `src/cadrumo/application/operator_surface/help.py`
- `M` `.vault/plan/2026-08-05-ci-lane-deconflation-plan.md`
- `A` `.vault/exec/2026-08-05-ci-lane-deconflation/2026-08-05-ci-lane-deconflation-P05-S166.md`

## Notes

- `uv run --no-sync ruff check src/cadrumo/application/operator_surface/help.py` emitted `All checks passed!` (exit 0); `ruff format --check` emitted `1 file already formatted` (exit 0).
- The direct root-help probe emitted `root help: 8 paragraphs, 5 sections, 22 entries` after asserting the first section's five commands and preserved ordering (exit 0).
- The exact AST probe measured `_root_help` at 168 lines and `_root_start_resume_section` at 27 lines (exit 0); no size baseline or policy changed.
- `uv run --no-sync pytest --collect-only -q src/cadrumo/entrypoints/cli/tests/test_root_payloads.py src/cadrumo/entrypoints/cli/tests/test_root_help_shape.py` collected 8 of 31 nodes with 23 project-marker deselections (exit 0). The focused payload run reported 7 passed and 1 failed (exit 1): unrelated `build_help_document("app")` localization is over the 80-character `HelpEntry.description` bound.
