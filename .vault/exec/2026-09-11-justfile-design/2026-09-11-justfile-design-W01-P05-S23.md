---
tags:
  - '#exec'
  - '#justfile-design'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:9b3cb7e111ea92bfc9af5b6104c99daf0ae1f4155e5ed2d7dff3ad625262433e'
step_id: 'S23'
related:
  - "[[2026-09-11-justfile-design-plan]]"
---

# Restrict fix recipes to mechanical source repair and move non-documentation committed derivatives to explicit generation verbs

## Scope

- `justfile`

## Changes

- `M` `justfile`
- `verify:` `uv run --no-sync ruff check dev/init dev/env dev/quality dev/audit dev/tests/test_write_path_coverage_gate.py` -> `pass`
- `verify:` `uv run --no-sync ruff format --check dev/init dev/env dev/quality dev/audit dev/tests/test_write_path_coverage_gate.py` -> `pass`
- `verify:` `just --dry-run fix-code` -> `pass`
- `verify:` `just --dry-run fix-style` -> `pass`
- `verify:` `just --dry-run fix-imports` -> `pass`
- `verify:` `just --dry-run fix-format` -> `pass`
- `verify:` `just --dry-run generate-corpus-text; just --dry-run generate-corpus-sidecars` -> `pass`
