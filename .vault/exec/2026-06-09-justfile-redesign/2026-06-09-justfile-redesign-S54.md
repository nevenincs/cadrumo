---
tags:
  - '#exec'
  - '#justfile-redesign'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:8e6487f2a55dddf471246417f23418370d46248b4f6aed07a0b765bea0f0724d'
step_id: 'S54'
related:
  - "[[2026-06-09-justfile-redesign-plan]]"
---
# Run focused justfile, workflow, initialization, and quality-suite verification

## Scope

- `justfile consumers`

## Changes

- `verify:` `uv run --no-sync pytest -q -n0 <focused command-surface tests>` -> `pass`
- `verify:` `uv run --no-sync ruff check <edited Python files>` -> `pass`
- `verify:` `just check-workflow` -> `pass`
