---
tags:
  - '#exec'
  - '#history-onboarding'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:35ccc7b7a6d7886a6f6fd3b6b3d9f4d6a67fb3584af0fed819d89e5ec5683bde'
step_id: 'S14'
related:
  - "[[2026-08-07-history-onboarding-plan]]"
---

# add the cross-period next_action builder cases pointing at the new discover and pull-all verbs, verified by the existing next-action conformance coverage

## Scope

- `src/cadrumo/application/modelo/_verification_cross_period.py`

## Description

- Add the `discover` and `pull-all` next-action mention to the cross-period fallback branch.

## Outcome

Confined to the FALLBACK branch on purpose. The targeted `pull-sources` verb stays
the action for a KNOWN upstream gap; a whole-history sweep is the right answer only
when the profile has no AEAT-sourced evidence at all, and offering it for a single
missing period would send the operator on a far longer run than the gap requires.
The reasoning is recorded beside the two constants so a later editor does not
"improve" it into every branch.

## Verification

uv run --no-sync pytest src/cadrumo/application/live/tests/ src/cadrumo/application/overview/tests/ \
      src/cadrumo/entrypoints/cli/tests/test_app_live_filed_discover.py \
      src/cadrumo/entrypoints/cli/tests/test_filed_history_onboarding_result.py \
      src/cadrumo/entrypoints/cli/tests/test_json_schema_conformance.py \
      src/cadrumo/entrypoints/cli/tests/test_documented_command_conformance.py \
      src/cadrumo/agent/tests/test_rule_surface_conformance.py -q -n0 -m "unit or integration"
    1147 passed, 2 deselected in 155.20s (0:02:35)

## Notes
