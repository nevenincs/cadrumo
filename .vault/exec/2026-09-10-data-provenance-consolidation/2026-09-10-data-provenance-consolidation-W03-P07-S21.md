---
tags:
  - '#exec'
  - '#data-provenance-consolidation'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:b2bb780a1e69967826019917890043fc4788edd36b1e3163c4fbe6a3cc65b72a'
step_id: 'S21'
related:
  - "[[2026-09-10-data-provenance-consolidation-plan]]"
---

# Remove duplicated payload, metadata, and derivative classification from the retired coverage sweep

## Scope

- `src/cadrumo/domain/calculations/registry/tests/test_corpus_provenance_coverage.py`

## Changes

- `verify:` `uv run pytest dev/registry/tests/test_corpus_provenance_coverage.py -q` -> `pass`

## Notes

- S08 already removed the retired sweep; S21 verified the retained catalog-backed detector module without further source edits.
