---
tags:
  - '#exec'
  - '#cli-verb-profile-diagnostics'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:8b8d55721b1a0d1199a0aad545c03af315a6df5ffc6606a04e73e49cd35fed42'
step_id: 'S01'
related:
  - "[[2026-08-09-cli-verb-profile-diagnostics-plan]]"
---
# Add a resolver mapping a declared model_selectors token to its section.field path, returning nothing when the token names no field or more than one

## Scope

- `src/cadrumo/domain/user_profile/_schema.py`

## Description

- Added `ProfileSchemaDefinition.path_for_model_selector`, returning the canonical `section.field` path of the single field declaring a given `model_selectors` token.
- Placed it as an instance method beside `section()` and `field()` rather than as a free function, because it is the inverse of a declaration the schema already owns and every other schema lookup is a method on the same class.
- Made both the unknown-token and ambiguous-token cases return `None` rather than raise: callers hold identifiers from mixed namespaces (deadline-engine gating keys, registry binding keys, genuine warning codes) and must be able to ask without first knowing which namespace they hold.

## Outcome

The inverse lookup that surfaces need in order to reach the canonical requirement builder now exists. A surface holding a selector token can obtain a real field path, and therefore the field's operator label and legal grounding, instead of rendering the token verbatim.

The ambiguity behaviour is a deliberate refusal, not a limitation worked around. The schema does not constrain a token to one declaring field, so a token declared twice has no single correct answer, and returning either candidate would confidently mislabel the other. Refusing means such a token degrades to the identifier the surface renders today rather than to a wrong label.

## Verification

    uv run --no-sync pytest src/cadrumo/domain/user_profile/tests/test_schema.py -n 0 -q
    13 passed in 11.12s

Covered by the tests added in the sibling Step, including a mutation probe proving the ambiguity assertion fails when the resolver is changed to return its first match.

## Notes

The originating Step row scoped only the resolver. The tests and the facade question are the two sibling Steps and are recorded there.
