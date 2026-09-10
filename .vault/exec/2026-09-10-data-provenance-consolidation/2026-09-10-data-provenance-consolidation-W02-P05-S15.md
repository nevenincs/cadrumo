---
tags:
  - '#exec'
  - '#data-provenance-consolidation'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:97bcc6ee6b51ac34473c82eb8e642b1d61d6f55e9aeb5c0889bbefeadde4cfb0'
step_id: 'S15'
related:
  - "[[2026-09-10-data-provenance-consolidation-plan]]"
---

# Migrate corpus-sidecar freshness checks to shared validation and catalog derivation

## Scope

- `dev/corpus/tests/test_extraction_sidecar_freshness.py`

## Changes

- `M` `dev/corpus/tests/test_extraction_sidecar_freshness.py`
- `verify:` `uv run --no-sync pytest dev/corpus/tests/test_extraction_sidecar_freshness.py::test_committed_extraction_sidecars_match_current_sources -q` -> `pass`

## Notes

Full-module validation is pre-existing red at the canonical-LF gate for six normative HTML files; baseline formatting also fails outside this Step's diff.
