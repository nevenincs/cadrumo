---
tags:
  - '#exec'
  - '#data-provenance-consolidation'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:3978da843b046783017ef807edb669a90373dab6f0a6d63f54d884dec0f850da'
step_id: 'S22'
related:
  - "[[2026-09-10-data-provenance-consolidation-plan]]"
---

# Remove duplicate generic full-tree sidecar validation after shared validator parity

## Scope

- `dev/corpus/tests/test_extraction_sidecar_freshness.py`

## Changes

- `M` `dev/corpus/tests/test_extraction_sidecar_freshness.py`
- `verify:` `uv run ruff check dev/corpus/tests/test_extraction_sidecar_freshness.py` -> `pass`

## Notes

- The full module retains a pre-existing canonical-LF fixture failure; focused retained tests exceeded the local command cap.
