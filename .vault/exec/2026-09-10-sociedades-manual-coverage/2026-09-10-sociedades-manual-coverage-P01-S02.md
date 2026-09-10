---
tags:
  - '#exec'
  - '#sociedades-manual-coverage'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:1ef2350431cf2b64ac034cea80152d5e1a73bdebe627d30e2efffc725cd6d9c7'
step_id: 'S02'
related:
  - "[[2026-09-10-sociedades-manual-coverage-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Project covered, unacquired, and unpublished annual-manual states from the catalogue

## Scope

- `src/cadrumo/application/registry/corpus.py`

## Changes
- `M` `src/cadrumo/application/registry/corpus.py`
- `M` `src/cadrumo/application/registry/tests/test_corpus.py`
- `verify:` `uv run pytest -n 0 src/cadrumo/application/registry/tests/test_corpus.py::test_manuals_list_report_localizes_the_unpublished_acquisition_condition -q --disable-warnings --maxfail=1` -> `pass`
