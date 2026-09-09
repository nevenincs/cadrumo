---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:41d98b3084581503a7400a7f75813bc7ee74522e58a9a49303eda6c758b08758'
step_id: 'S297'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Delete the dev-wide governance-corpus isolation census and its eleven path-keyed exemptions; retain the strict no-allowlist src isolation gate and shared detector.

## Scope

- `development governance isolation test`
- `production isolation gate`
- `exact reachability`
- `cadence reference`
- `and Step Record`

## Changes

- `D` `dev/tests/test_dev_governance_isolation.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync pytest -q dev/tests/test_governance_corpus_isolation.py` -> `pass`
- `verify:` `rg -n <deleted dev-isolation identifiers> src dev justfile pyproject.toml` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `pass`

## Notes

The retained strict production-boundary suite passed all 37 tests. Exact reachability remained at 243 unused symbols, 31 unreachable modules, and zero orphan tests; deleting the dev-only census changes no shipped edge.
