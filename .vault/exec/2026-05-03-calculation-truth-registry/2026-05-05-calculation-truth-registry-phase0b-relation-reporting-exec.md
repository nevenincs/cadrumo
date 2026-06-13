---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-05'
modified: '2026-05-05'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
---

# `calculation-truth-registry` `phase0b` `relation-reporting`

Registry relation reporting for dependency audit.

- Modified: `src/aeat/entrypoints/cli/registry.py`
- Modified: `src/aeat/entrypoints/cli/test_registry_cli.py`
- Modified: `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md`

## Description

The registry inspect and verify reports now expose relation counts and relation
dependency roles at both the whole-tree level and per-revision level. This lets
the implementation plan track whether dependency work is represented by the
central registry instead of relying on manual file inspection.

The CLI tests verify the committed registry reports the Modelo 180 periodic
summary dependency role and that per-revision relation counts match the
reported relation identifiers.

## Tests

- `uv run pytest src/aeat/entrypoints/cli/test_registry_cli.py -q`
- `uv run ruff check src/aeat/entrypoints/cli/registry.py src/aeat/entrypoints/cli/test_registry_cli.py`
- `uv run ruff format --check src/aeat/entrypoints/cli/registry.py src/aeat/entrypoints/cli/test_registry_cli.py`
- `uv run ty check src/aeat/entrypoints/cli/registry.py src/aeat/entrypoints/cli/test_registry_cli.py`
- `uv run aeat app registry verify --registry-root registry\aeat --source-root . --json`
