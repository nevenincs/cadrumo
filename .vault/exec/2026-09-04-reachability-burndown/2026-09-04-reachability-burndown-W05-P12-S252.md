---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:f383fc1ea428f70ce166b2e88acfadab00466e6ea1535f53584110cabab8045a'
step_id: 'S252'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Delete the unwired portal-drift model and synthetic preflight injection path

## Scope

- `Keep portal-registry assembly health`
- `remove the type-only drift DTO and evaluator plus tests that manufactured observations no product path captures`
- `run portal and preflight gates`
- `remeasure exact reachability`
- `update the cadence reference`
- `and write the Step Record`

## Changes

- `M` `src/cadrumo/application/preflight.py`
- `M` `src/cadrumo/application/tests/test_preflight.py`
- `D` `src/cadrumo/domain/portals/drift.py`
- `D` `src/cadrumo/domain/portals/tests/test_drift.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync ruff check src/cadrumo/application/preflight.py src/cadrumo/application/tests/test_preflight.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/application/tests/test_preflight.py src/cadrumo/domain/portals/tests` -> `fail`
- `verify:` `uv run --no-sync pytest -q -n0 src/cadrumo/application/tests/test_preflight.py -k portal_health` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `fail`

## Notes

The combined preflight and portal suite reached 83 passing tests and one unrelated failure in `test_corpus_row_healthy_for_bundled_normatives`; the current bundled normative corpus probe returned unhealthy. The focused portal-health owner test passes, and this Step did not modify corpus data or its probe.
