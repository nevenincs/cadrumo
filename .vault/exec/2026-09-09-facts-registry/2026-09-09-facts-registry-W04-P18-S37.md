---
tags:
  - '#exec'
  - '#facts-registry'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:60d29c78dfc513e35ef932c69fb47e1fbc55dc29871c272ee7ee3a052de13ef5'
step_id: 'S37'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---
# Block provenance-free results and unresolved migration entries

## Scope

- `dev/registry/analysis`

## Changes

- `M` `dev/registry/analysis/facts_catalogue_quality.py`
- `M` `dev/registry/tests/test_facts_catalogue_quality.py`
- `verify:` `uv run --no-sync ruff check dev/registry/analysis/facts_catalogue_quality.py dev/registry/tests/test_facts_catalogue_quality.py` -> `pass`
- `verify:` `uv run --no-sync pytest -n 0 dev/registry/tests/test_facts_catalogue_quality.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.registry.analysis.facts_catalogue_quality` -> `pass`

## Notes

- S80/S85 holds are required only while their exact plan step remains open. A closed step requires the matching raw hold to be absent.
