---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:a8f3edd29e7c30bf5fa796bfd922193cabde91a1b23d476eca52815983845fcf'
step_id: 'S353'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the unrouted five-stage profile journey and its closed dev fixture registry/test loop while retaining the live profile overview and application presentation owners.

## Scope

- `profile journey screen`
- `journey rendering`
- `dev profile fixtures`
- `presentation and overview gates`
- `exact reachability`

## Changes

- `D` `src/cadrumo/entrypoints/tui/profile/app.py`
- `D` `src/cadrumo/entrypoints/tui/profile/journey_status.py`
- `D` `src/cadrumo/entrypoints/tui/profile/tests/test_profile_journey.py`
- `D` `dev/tui/harness/profile_fixtures.py`
- `D` `dev/tui/harness/tests/test_profile_fixtures.py`
- `M` `dev/tui/harness/surfaces.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync pytest src/cadrumo/application/user_profile/tests/test_presentation.py src/cadrumo/application/user_profile/tests/test_overview.py src/cadrumo/entrypoints/tui/profile/tests/test_acquisition_source_capability.py -q` -> `pass (25 passed)`
- `verify:` `uv run --no-sync ruff check dev/tui/harness/surfaces.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `pass (20 unreachable modules; down from 22)`

## Notes

The broad dev harness run reached 66 passes but collection remains red because peer-owned `workbench_fixtures.py` imports the removed `OperationReplayStatus`; that unrelated fixture drift predates and does not import the deleted profile journey.
