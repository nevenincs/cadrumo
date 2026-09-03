---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:d7f72a2ebaa71e538bdc71d27c3167a88fc560363003df086b6e951a2d1e46b1'
step_id: 'S400'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# Build the child-owned installed-workbench generation provider from secure profile repositories and application projection builders, representing authorities without production loaders as explicit unavailable or never-captured sources rather than empty fixtures

## Scope

- `src/cadrumo/application/workbench_generation.py`
- `src/cadrumo/entrypoints/tui/launcher.py`
- `and focused production-composition tests`

## Changes

- `M` `src/cadrumo/application/workbench_generation.py`
- `M` `src/cadrumo/application/tests/test_workbench_generation.py`
- `M` `src/cadrumo/entrypoints/tui/launcher.py`
- `M` `src/cadrumo/entrypoints/tui/tests/test_installed_generation_composition.py`
- `M` `src/cadrumo/entrypoints/tui/tests/test_launcher_entry_point.py`
- `M` `.vault/audit/2026-09-03-tui-architecture-w08-p28-s400-review-audit.md`
- `verify:` `uv run pytest -q src/cadrumo/application/tests/test_workbench_generation.py src/cadrumo/entrypoints/tui/tests/test_installed_generation_composition.py src/cadrumo/entrypoints/tui/tests/test_launcher_entry_point.py src/cadrumo/entrypoints/tui/tests/test_launcher_composition_root.py src/cadrumo/entrypoints/tui/declarations/tests/test_declarations_workspace.py` -> `pass`
- `verify:` `uv run ruff check` and `uv run ruff format --check` on owned paths -> `pass`
- `verify:` `uv run ty check src/cadrumo/application/workbench_generation.py src/cadrumo/entrypoints/tui/launcher.py` -> `pass`
- `verify:` `uv run basedpyright src/cadrumo/application/workbench_generation.py src/cadrumo/entrypoints/tui/launcher.py` -> `pass`
- `verify:` targeted `dev.audit.duplication.run_duplication_scan` on both owned production files -> `pass`
- `verify:` `uv run python -m dev.quality.unreachable_module_ratchet` plus exact target scan -> `pass`
- `verify:` `uv run python -m cadrumo.entrypoints.tui` -> `pass`
