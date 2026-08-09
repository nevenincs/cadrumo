---
tags:
  - '#exec'
  - '#cli-verb-profile-diagnostics'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:de5bd49853b38a7b6e71ccf0af7ff856e11995d29f3ffebfb73f3d94d545b507'
step_id: 'S40'
related:
  - "[[2026-08-09-cli-verb-profile-diagnostics-plan]]"
---
# Extend the live-auth refusal tests to cover the Cl@ve identity and contraste field renderings

## Scope

- `src/cadrumo/application/auth/tests/test_session_identity_refusal_grounding.py`

## Description

- Added a parametrised anchor asserting each of the three Cl@ve field labels differs from its path.
- Added a parametrised assertion that no rendering is, or contains, its storage path.

## Outcome

All three fields are covered against the real committed schema.

The containment check is the meaningful one for these fields specifically. They declare no selectors, so their labels resolve from the path alone, and the requirement builder's documented behaviour on an unresolved field is to return the argument unchanged - meaning a broken resolution would produce exactly the path. Asserting the path is absent is therefore the assertion that separates a resolved label from a silent fallback.

## Verification

    uv run --no-sync pytest src/cadrumo/application/auth/tests/test_session_identity_refusal_grounding.py -n 0 -q
    9 passed in 2.38s

    uv run --no-sync pytest src/cadrumo/application/auth -m "unit or integration" -n 0 -q
    319 passed in 75.35s (0:01:15)

## Notes

A third assertion written in the first draft was removed rather than kept: its condition was constructed so that it could not meaningfully fail, and the two retained assertions already cover what it was reaching for.
