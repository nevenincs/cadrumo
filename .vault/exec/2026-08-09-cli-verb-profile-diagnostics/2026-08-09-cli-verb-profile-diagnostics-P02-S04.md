---
tags:
  - '#exec'
  - '#cli-verb-profile-diagnostics'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:378a559013bd5f065dc6b2a2506319486c19109f9dca016a1919f72e8e8d2329'
step_id: 'S04'
related:
  - "[[2026-08-09-cli-verb-profile-diagnostics-plan]]"
---
# Add a shared refusal-rendering helper that enriches profile-selector warning codes into schema-derived requirement rows and passes non-profile codes through unchanged

## Scope

- `src/cadrumo/entrypoints/cli/_overview.py`

## Description

- Promoted the existing private requirement formatter out of the modelo readiness gate into the canonical preflight module as `format_profile_preflight_requirement`, and pointed the readiness gate at it. There is now one rendering of a missing profile requirement rather than one per surface.
- Added `format_profile_selector_requirements` beside it, bridging surfaces that hold a declared selector TOKEN rather than a `section.field` path. It resolves each token through the schema resolver, feeds resolved paths to the canonical requirement builder, and passes unresolved tokens through unchanged.
- Exported both through the package facade.
- Added `_grounded_warning_summary` and `_incomplete_profile_refusal` to the overview CLI module, the latter raising a refusal rather than a Click parameter error, and offering a remediation command only when every warning agrees on one.

## Outcome

The three overview verbs now share one refusal builder, and that builder reaches the same schema and registry authority the modelo readiness gate consults.

Two choices are worth stating because the alternative was tempting:

The formatter was MOVED, not copied. Writing a second renderer in the CLI layer would have been smaller, and would have produced a surface where the readiness gate and the overview refusal drift apart on how they present the same missing field.

Unresolved tokens pass through instead of being labelled. The warning stream genuinely mixes namespaces - censo enrolment and evidence-conflict codes are not profile fields and have no label to show. Passing them through preserves exactly what the surface showed before, whereas guessing a label for them would be confidently wrong.

The suggestion is offered only on unanimity. Naming one of several fix commands would send the operator to a command resolving only part of what blocks them.

## Verification

    uv run --no-sync pytest src/cadrumo/application/modelo/tests/test_profile_readiness_gate.py src/cadrumo/application/user_profile/tests/test_services.py -n 0 -q
    41 passed in 14.18s

That run covers the formatter move: the readiness gate's own refusal tests exercise the promoted function through its new home.

## Notes

The formatter promotion was not in the Step row as written. It was taken because the row's own requirement - route the overview through the canonical mechanism - could otherwise only have been met by duplicating the renderer, which this project's rules forbid.
