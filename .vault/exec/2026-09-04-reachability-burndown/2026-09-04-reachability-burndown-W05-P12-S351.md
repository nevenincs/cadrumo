---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:0bdde8a044da03565e28c6736e37177bdfa11711fb509e419aa7ec171f106511'
step_id: 'S351'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Remove the unreachable legacy Textual flow frontend and its test/dev-only fixtures, including the embedded Python subprocess program, while retaining canonical application-flow and CLI behavior coverage.

## Scope

- `src/cadrumo/entrypoints/tui/flows`
- `src/cadrumo/entrypoints/tui/tests`
- `dev/tui/harness`

## Changes

- `D` `src/cadrumo/entrypoints/tui/flows/__init__.py`
- `D` `src/cadrumo/entrypoints/tui/flows/_question_pane.py`
- `D` `src/cadrumo/entrypoints/tui/flows/_review_pane.py`
- `D` `src/cadrumo/entrypoints/tui/flows/app.py`
- `D` `src/cadrumo/entrypoints/tui/flows/tests/__init__.py`
- `D` `src/cadrumo/entrypoints/tui/flows/tests/test_guided_flow_pages.py`
- `D` `src/cadrumo/entrypoints/tui/flows/tests/test_guided_flows.py`
- `D` `src/cadrumo/entrypoints/tui/tests/test_flow_tui_app.py`
- `D` `src/cadrumo/entrypoints/tui/tests/test_frontend_parity.py`
- `D` `dev/tui/harness/modelo_work_wizard.py`
- `M` `dev/tui/harness/surfaces.py`
- `M` `src/cadrumo/entrypoints/tui/tests/test_terminal_sizes.py`
- `M` `src/cadrumo/entrypoints/tui/tests/test_visual_verification.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync pytest src/cadrumo/application/flows/tests src/cadrumo/entrypoints/cli/tests/test_modelo_work_wizard.py src/cadrumo/entrypoints/cli/tests/test_modelo_amend_wizard.py -q` -> `pass`
- `verify:` `uv run --no-sync pytest dev/tui/harness/tests/test_modelo_fixtures.py src/cadrumo/entrypoints/tui/tests/test_terminal_sizes.py -q` -> `pass`
- `verify:` `uv run --no-sync ruff check src/cadrumo/entrypoints/tui/tests/test_visual_verification.py src/cadrumo/entrypoints/tui/tests/test_terminal_sizes.py dev/tui/harness/surfaces.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `pass (24 unreachable modules; down from 28)`
