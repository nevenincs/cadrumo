---
tags:
  - '#exec'
  - '#history-onboarding'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:3b3b16c030d3c877e70060a057d0c1434160621326a4780ae92c88691e69250a'
step_id: 'S15'
related:
  - "[[2026-08-07-history-onboarding-plan]]"
---

# update operator_surface/_help.py with the new discover and pull-all verb entries, verified by test_rule_surface_conformance.py

## Scope

- `src/cadrumo/application/operator_surface/_help.py`

## Description

- Add the `discover` and `pull-all` entries to the operator help surface.

## Outcome

Both verbs join the existing live-reads section beside `filed list`, `filed pull`
and `filed pull-sources`, so an operator reading the help finds the history pull
where the rest of the filed group already is.

## Verification

uv run --no-sync pytest src/cadrumo/application/live/tests/ src/cadrumo/application/overview/tests/ \
      src/cadrumo/entrypoints/cli/tests/test_app_live_filed_discover.py \
      src/cadrumo/entrypoints/cli/tests/test_filed_history_onboarding_result.py \
      src/cadrumo/entrypoints/cli/tests/test_json_schema_conformance.py \
      src/cadrumo/entrypoints/cli/tests/test_documented_command_conformance.py \
      src/cadrumo/agent/tests/test_rule_surface_conformance.py -q -n0 -m "unit or integration"
    1147 passed, 2 deselected in 155.20s (0:02:35)

## Notes
