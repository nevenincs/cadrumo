---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:730b0b6ddcda351ecd9a00bb38218ff6411a2d9a960fb353d0f33896583c5b57'
step_id: 'S224'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the duplicate overview verb-roster census and its command_spec_nodes dependency from the explain integration suite, retaining the canonical CommandSpec exact-set gate and every real CLI explain behavior test so the orphan walker follows the live CLI runner support edge instead of mistaking a material suite for a test of one unused projection.

## Scope

- `Overview explain integration tests`
- `canonical overview CommandSpec tests and accepted command-spec authority`
- `orphan-test support-hop detector behavior`
- `exact reachability signal`
- `cadence reference`
- `Step Record`
- `and independent code review.`

## Changes

- `M` `.vault/plan/2026-09-04-reachability-burndown-plan.md`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `M` `src/cadrumo/entrypoints/cli/tests/test_overview_explain_verb.py`
- `A` `.vault/exec/2026-09-04-reachability-burndown/2026-09-04-reachability-burndown-W05-P12-S224.md`
- `verify:` `uv run --no-sync ruff check src/cadrumo/entrypoints/cli/tests/test_overview_explain_verb.py src/cadrumo/entrypoints/cli/tests/test_overview_command_specs.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n 0 --basetemp .tmp/pytest-s224 src/cadrumo/entrypoints/cli/tests/test_overview_command_specs.py src/cadrumo/entrypoints/cli/tests/test_overview_explain_verb.py` -> `pass (3 passed, 6 integration tests deselected)`
- `verify:` `uv run --no-sync pytest -q -n 0 -m integration --basetemp .tmp/pytest-s224-integration src/cadrumo/entrypoints/cli/tests/test_overview_explain_verb.py` -> `pass (6 passed)`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `pass (expected nonzero with live findings: 60 unreachable modules, 307 exact unused symbols, 9 orphaned tests, 2029/2090 shipped modules reachable)`
