---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:9bf1a10992a3f66e09c3a4eae84da11739aef722035b9abaca608779e27bca84'
step_id: 'S355'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Delete the displaced Modelo TUI action/edit/review/select generation and its synthetic helpers, fixture registries, and registry-completeness detector while retaining the routed installed workspace and application owners.

## Scope

- `19 exact unreachable modules`
- `associated TUI tests and dev fixtures`
- `installed workspace and edit/CLI gates`
- `exact reachability`

## Changes

- `D` `src/cadrumo/entrypoints/tui/modelo/action/__init__.py`
- `D` `src/cadrumo/entrypoints/tui/modelo/action/amend.py`
- `D` `src/cadrumo/entrypoints/tui/modelo/action/discard.py`
- `D` `src/cadrumo/entrypoints/tui/modelo/action/export.py`
- `D` `src/cadrumo/entrypoints/tui/modelo/action/file.py`
- `D` `src/cadrumo/entrypoints/tui/modelo/action/rename.py`
- `D` `src/cadrumo/entrypoints/tui/modelo/action/verify.py`
- `D` `src/cadrumo/entrypoints/tui/modelo/actions.py`
- `D` `src/cadrumo/entrypoints/tui/modelo/edit/__init__.py`
- `D` `src/cadrumo/entrypoints/tui/modelo/edit/controller.py`
- `D` `src/cadrumo/entrypoints/tui/modelo/edit/fields.py`
- `D` `src/cadrumo/entrypoints/tui/modelo/edit/review.py`
- `D` `src/cadrumo/entrypoints/tui/modelo/edit/rows.py`
- `D` `src/cadrumo/entrypoints/tui/modelo/edit/screen.py`
- `D` `src/cadrumo/entrypoints/tui/modelo/view/work_review.py`
- `D` `src/cadrumo/entrypoints/tui/modelo/view/work_select.py`
- `D` `src/cadrumo/application/modelo/edit_session.py`
- `D` `src/cadrumo/entrypoints/tui/components/form_screen.py`
- `D` `src/cadrumo/entrypoints/tui/components/keyboard.py`
- `D` `src/cadrumo/application/modelo/tests/test_edit_session.py`
- `D` `src/cadrumo/entrypoints/tui/components/tests/test_form_screen.py`
- `D` `src/cadrumo/entrypoints/tui/modelo/edit/tests/__init__.py`
- `D` `src/cadrumo/entrypoints/tui/modelo/edit/tests/test_controller.py`
- `D` `src/cadrumo/entrypoints/tui/modelo/edit/tests/test_fields.py`
- `D` `src/cadrumo/entrypoints/tui/modelo/edit/tests/test_rows_and_review.py`
- `D` `src/cadrumo/entrypoints/tui/modelo/tests/test_actions.py`
- `D` `src/cadrumo/entrypoints/tui/modelo/tests/test_c1_bounded_review.py`
- `D` `src/cadrumo/entrypoints/tui/modelo/tests/test_c3_editor_accessibility.py`
- `D` `src/cadrumo/entrypoints/tui/modelo/tests/test_c3_editor_screen.py`
- `D` `src/cadrumo/entrypoints/tui/modelo/tests/test_c4_action_accessibility.py`
- `D` `src/cadrumo/entrypoints/tui/modelo/tests/test_c4_amend_action.py`
- `D` `src/cadrumo/entrypoints/tui/modelo/tests/test_c4_discard_action.py`
- `D` `src/cadrumo/entrypoints/tui/modelo/tests/test_c4_export_action.py`
- `D` `src/cadrumo/entrypoints/tui/modelo/tests/test_c4_file_action.py`
- `D` `src/cadrumo/entrypoints/tui/modelo/tests/test_c4_rename_action.py`
- `D` `src/cadrumo/entrypoints/tui/modelo/tests/test_c4_verify_action.py`
- `D` `src/cadrumo/entrypoints/tui/modelo/view/tests/test_work_review.py`
- `D` `src/cadrumo/entrypoints/tui/modelo/view/tests/test_work_select.py`
- `D` `dev/tui/harness/modelo_fixtures.py`
- `D` `dev/tui/harness/tests/test_modelo_fixtures.py`
- `D` `dev/tui/harness/tests/test_every_fixture_registry_is_registered.py`
- `M` `dev/tui/harness/surfaces.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync pytest -n0 -m "" src/cadrumo/application/modelo/tests/test_edit_services.py src/cadrumo/application/modelo/tests/test_edit_execution.py src/cadrumo/entrypoints/cli/tests/test_modelo_work_review_envelope.py -q` -> `pass (21 passed)`
- `verify:` `uv run --no-sync pytest -n0 -m "" src/cadrumo/entrypoints/tui/modelo/view/tests/test_installed_workspace.py -q` -> `pass (2 passed)`
- `verify:` `uv run --no-sync ruff check dev/tui/harness/surfaces.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `pass (0 unreachable modules; down from 19)`
