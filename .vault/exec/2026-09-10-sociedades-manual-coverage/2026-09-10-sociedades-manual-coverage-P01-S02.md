---
tags:
  - '#exec'
  - '#sociedades-manual-coverage'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:f65490f93da9e9139c3d62d23c426ba95b02029d7b5d2a6b58353e57cd1abaeb'
step_id: 'S02'
related:
  - "[[2026-09-10-sociedades-manual-coverage-plan]]"
---

# Project covered, unacquired, and unpublished annual-manual states from the catalogue

## Scope

- `src/cadrumo/application/registry/corpus.py`

## Changes
- `M` `src/cadrumo/application/registry/corpus.py`
- `M` `src/cadrumo/application/registry/tests/test_corpus.py`
- `verify:` `uv run pytest -n 0 src/cadrumo/application/registry/tests/test_corpus.py::test_manuals_list_report_localizes_the_unpublished_acquisition_condition -q --disable-warnings --maxfail=1` -> `pass`
