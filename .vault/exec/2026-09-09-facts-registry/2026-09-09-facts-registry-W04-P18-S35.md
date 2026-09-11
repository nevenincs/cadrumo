---
tags:
  - '#exec'
  - '#facts-registry'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:17d9e4c34f4df5ca5d8cb2286b5428c8529184a8655a31b773d7f804c6f932ab'
step_id: 'S35'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---
# Block imports of retired declarations and loader symbols

## Scope

- `dev/quality`

## Changes

- `A` `dev/quality/tests/test_retired_fact_authority_imports.py`
- `verify:` `uv run --no-sync ruff check dev/quality/tests/test_retired_fact_authority_imports.py` -> `pass`
- `verify:` `uv run --no-sync pytest -n 0 dev/quality/tests/test_retired_fact_authority_imports.py` -> `pass`

## Notes

- The census forbids only already retired modules and raw convenio symbols. It permits the canonical convenio projection and pending IVA grounding, whose removal is gated by S81-S85.
