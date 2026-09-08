---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:78f9ac7a665bc5bde86ea9897fcc7531b6489da0b8ef1c1461d35cb3fa1c7653'
step_id: 'S255'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Delete the unused terminology exact-lookup facade and its test-only assertion

## Scope

- `Retain the live approved-concept search and strict loader`
- `remove the uncalled lookup export and prose`
- `keep lifecycle filtering proof over loaded concepts`
- `run focused corpus-search gates`
- `remeasure exact reachability`
- `update the cadence reference`
- `and write the Step Record`

## Changes

- `M` `src/cadrumo/application/corpus_search/terminology.py`
- `M` `src/cadrumo/application/corpus_search/tests/test_terminology_lifecycle.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync ruff check src/cadrumo/application/corpus_search/terminology.py src/cadrumo/application/corpus_search/tests/test_terminology_lifecycle.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n0 src/cadrumo/application/corpus_search/tests/test_terminology_lifecycle.py src/cadrumo/application/corpus_search/tests/test_terminology_fragment_shape.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/application/corpus_search/tests` -> `fail`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `fail`

## Notes

The full corpus-search suite had 43 passes and five unrelated Windows parallel scratch failures around shared pytest directories and SQLite files. The serial terminology owner suite passes all 11 tests, and exact reachability removed the lookup symbol.
