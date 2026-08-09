---
tags:
  - '#exec'
  - '#cli-verb-profile-diagnostics'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:084238e14c422d5ba508d6642cf9d343dfc23a174b871251b8c321881ec2dfb9'
step_id: 'S03'
related:
  - "[[2026-08-09-cli-verb-profile-diagnostics-plan]]"
---
# Add real-schema tests covering a resolving token, an absent token and an ambiguous token

## Scope

- `src/cadrumo/domain/user_profile/tests/test_schema.py`

## Description

- Added a resolution test asserting the committed schema's `has_employees` token resolves to `withholding.has_employees`, and that the resolved field really declares that token.
- Added a whole-corpus property test: every token declared anywhere in the committed schema either resolves to nothing or resolves to a field carrying that exact token. This is the assertion that would catch the failure that actually matters, a confidently wrong path.
- Added an absent-token test covering an unknown token, the empty string and a whitespace-only string.
- Added an ambiguity test that constructs a two-field section sharing one token, because the committed schema declares each token exactly once and cannot express the divergence being tested.

## Outcome

The resolver's three behaviours are covered against the real committed schema wherever real data can express them, and against a constructed schema only where it cannot.

The whole-corpus test is deliberately written as a property over the declared token set rather than as a fixed expected count. A count would encode today's schema and would train the next author to update a constant instead of reading the failure.

The ambiguity test carries its own positive control: after asserting the ambiguous token resolves to nothing, it asserts an unambiguous token still resolves correctly on the same constructed schema. Without that, a resolver broken outright by the added section would produce the same `None` and read as a pass.

## Verification

    uv run --no-sync pytest src/cadrumo/domain/user_profile/tests/test_schema.py -n 0 -q
    13 passed in 11.12s

Mutation probe, applied at runtime from outside the repository so no tracked file was modified, replacing the resolver with one returning its first match:

    MUTATION APPLIED: resolver returns first match instead of refusing ambiguity
    1 failed, 1 passed, 11 deselected in 0.78s

The failure was the ambiguity assertion, reporting `assert 'ambiguity_probe.first_declaring_field' is None`. The gate bites.

## Notes

The first run of the ambiguity test failed on model construction rather than on its assertion: the strict frozen models reject a list where a tuple is declared. Corrected to tuples. Worth noting because a strict-model construction error surfaces as a test failure that looks like a behavioural finding and is not one.
