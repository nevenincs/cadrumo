---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:d43c7c1e813bdd01d798210343a2a71588f5bb1853d4201d0ce91308855f3664'
step_id: 'S228'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the zero-consumer unapprove_draft writer and the two documentation claims that publish it as a supported review transition; preserve approval invalidation and the accepted immutable-revision recovery rule, where recovery creates an explicit successor rather than clearing approval metadata in place.

## Scope

- `Filing draft review implementation and package documentation`
- `accepted evidence revision identity decision`
- `exact symbol signal`
- `focused approval and supersession gates`
- `cadence reference`
- `Step Record`
- `and independent code review.`

## Changes

- `M` `src/cadrumo/application/filing/draft_review.py`
- `M` `src/cadrumo/application/filing/__init__.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync ruff check src/cadrumo/application/filing/draft_review.py src/cadrumo/application/filing/__init__.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n 0 --basetemp .tmp/pytest-s228 src/cadrumo/application/filing/tests/test_filing.py src/cadrumo/application/filing/tests/test_review_runtime_storage.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `fail`

## Notes

The exact audit exits 1 on the remaining backlog, as designed. This step reduced reachable-module unused-symbol findings from 306 to 305 while leaving 51 unreachable modules and four orphaned test modules unchanged. Exact code/dev search found no surviving `unapprove_draft` reference before or after deletion; the package facade is inert and had only advertised the unsupported transition in prose.
