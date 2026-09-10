---
tags:
  - '#exec'
  - '#sociedades-manual-coverage'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:ed81c84ed0ef81f05d9ee3514fd95fcd4857e321bf34bb2224abc3e050cb5316'
step_id: 'S09'
related:
  - "[[2026-09-10-sociedades-manual-coverage-plan]]"
---

# Regenerate the CLI reference and Pagefind inputs from the live localized command graph

## Scope

- `dev/docs`

## Changes

- `M` `docs/cli/app/registry.rst`
- `M` `docs/_static/cli-tree.json`
- `M` `dev/docs/tests/test_cli_tree.py`
- `verify:` `uv run pytest dev/docs/tests/test_cli_reference_pages_are_not_stubs.py dev/docs/tests/test_cli_anchor_parity.py` -> `pass`
- `verify:` `uv run pytest dev/docs/tests/test_cli_tree.py -k "sociedades_manual_list or projection_covers_every_collected_path or write_cli_tree_emits_default_static_path" dev/docs/tests/test_sequence_build_gate.py` -> `pass`
