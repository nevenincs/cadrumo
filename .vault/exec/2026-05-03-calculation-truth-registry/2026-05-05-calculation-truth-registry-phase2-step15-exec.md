---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-05'
modified: '2026-05-05'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
---


# `calculation-truth-registry` `phase2` `step15`

Removed concrete modelo IDs from registry CLI tests.

- Modified: `src/aeat/entrypoints/cli/test_registry_cli.py`
- Modified: `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md`

## Description

Registry CLI tests now derive the committed modelo ids and application-link
surfaces from the registry TOML tree. The tests still exercise the same CLI
inventory, verification, workbook, selection, and authentication-failure
behaviour, but they no longer encode handpicked modelo ids as test authority.

## Tests

- `uv run pytest src\aeat\entrypoints\cli\test_registry_cli.py -q`
  passed: 11 tests.
- `uv run ruff check src\aeat\entrypoints\cli\registry.py src\aeat\entrypoints\cli\test_registry_cli.py`
  passed.
- `uv run ty check src\aeat\entrypoints\cli\registry.py src\aeat\entrypoints\cli\test_registry_cli.py`
  passed.
