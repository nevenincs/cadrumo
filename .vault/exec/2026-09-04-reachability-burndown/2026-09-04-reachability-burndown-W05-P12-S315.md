---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:6c157c3bfd1162bfa4eb62f84af29b8cdb660fd00702b312422f13f041bfe1d8'
step_id: 'S315'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Delete the live-filename magic-banner lint and embedded test modules

## Scope

- `filename marker lint`
- `live test collection`
- `exact reachability`
- `cadence reference`
- `and Step Record`

## Changes

- `D` `src/cadrumo/tests/test_filename_live_marker_lint.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync pytest --collect-only -q -n0 -o addopts='' src/cadrumo/application/live/tests` -> `pass`
