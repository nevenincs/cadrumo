---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:c7b78ce68030b0beb6ba856cccc9813cc26befcbdf817aa096777e2cf38d5204'
step_id: 'S111'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Wire the profile journey shell into the devtools surfaces with a schema-derived presentation fixture, closing its coverage gap

## Scope

- `src/cadrumo/entrypoints/tui/devtools/surfaces.py`

## Changes

- `A` `src/cadrumo/entrypoints/tui/devtools/profile_fixtures.py`
- `M` `src/cadrumo/entrypoints/tui/devtools/surfaces.py`
- `verify:` `uv run --no-sync python -m pytest src/cadrumo/entrypoints/tui/devtools/tests dev/tui/tests -n0` -> `pass`
- `verify:` `uv run --no-sync python -m dev.tui inventory` -> `pass`
- `verify:` `uv run --no-sync ty check src/cadrumo/entrypoints/tui/devtools/profile_fixtures.py` -> `pass`

## Notes

The gate added two steps earlier caught this work in progress: with the fixture
registry written and not yet spread into `SURFACES`, it named all three new
fixture ids and failed. That is its detector teeth demonstrated against live
code rather than a synthetic fixture.

The TUI review inventory reports 60 interfaces, 17 not rendered, down from 18.
Nothing fails on that number today; it is a named backlog the coverage tool
derives from source, and the dispositions in `dev/tui/_coverage.py` distinguish
a development-only candidate from a gap to close.

`python -m dev.tui inventory` refuses outright when a review run on disk carries
an older manifest schema, although its own docstring says coverage is read from
the coverage table alone when no manifest exists. The reading above was taken by
naming a run with no manifest. Left as found: the tool belongs to another
surface and the refusal is fail-closed, not wrong.
