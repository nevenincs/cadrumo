---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:b2b20f1a87cf6c7752863ee5a55279901184d3d26be1799a53d4224929c8de32'
step_id: 'S402'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# Expose one operation composition result containing services and the exact public contract set from the same registry so workbench actions and modals cannot drift

## Scope

- `src/cadrumo/application/operations/composition.py`
- `src/cadrumo/entrypoints/tui/launcher.py`
- `and focused composition tests`

## Changes

- `M` `src/cadrumo/application/operations/composition.py`
- `M` `src/cadrumo/application/operations/registry.py`
- `M` `src/cadrumo/entrypoints/tests/test_operation_composition.py`
- `M` `src/cadrumo/entrypoints/tui/launcher.py`
- `M` `src/cadrumo/entrypoints/tui/tests/test_installed_generation_composition.py`
- `M` `src/cadrumo/entrypoints/tui/tests/test_launcher_composition_root.py`
- `M` `src/cadrumo/entrypoints/tui/tests/test_launcher_entry_point.py`
- `M` `.vault/audit/2026-09-03-tui-architecture-w08-p28-s402-review-audit.md`
- `verify:` `pytest -q -n0 -m 'unit or integration' src/cadrumo/entrypoints/tests/test_operation_composition.py src/cadrumo/entrypoints/tui/tests/test_launcher_composition_root.py src/cadrumo/entrypoints/tui/tests/test_installed_generation_composition.py src/cadrumo/entrypoints/tui/tests/test_launcher_entry_point.py` -> `pass`
