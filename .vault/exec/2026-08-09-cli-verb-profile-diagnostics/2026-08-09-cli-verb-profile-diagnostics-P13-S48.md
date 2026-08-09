---
tags:
  - '#exec'
  - '#cli-verb-profile-diagnostics'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:c15eb45807ef2c798452010b2823f7fc06c812c6740f19eea23a7b2554279991'
step_id: 'S48'
related:
  - "[[2026-08-09-cli-verb-profile-diagnostics-plan]]"
---
# Add tests proving both binding-key sites render a real operator label and that the selector-based renderer would not have

## Scope

- `src/cadrumo/application/user_profile/tests/test_requirement_rendering_paths.py`

## Description

- Added paired tests asserting a selector token resolves ONLY through the selector renderer and a schema path resolves ONLY through the path renderer.
- Added a test that a real committed binding key renders as a label through the path renderer.
- Added a test pinning explicitly that the selector renderer leaves that same binding key raw.

## Outcome

The distinction between the two renderers is now a tested contract rather than an unwritten assumption.

The last test is the one that would have caught the original defect. It asserts the WRONG renderer produces the raw key, which is the observable signature of the no-op that shipped. A suite testing only that each renderer works in isolation would still permit a caller to pick the wrong one.

## Verification

    uv run --no-sync pytest src/cadrumo/application/user_profile/tests/test_requirement_rendering_paths.py -n 0 -q
    4 passed in 8.98s

Mutation probe reverting the path renderer to the selector lookup:

    MUTATION APPLIED: path renderer reverted to selector lookup
    4 failed, 3 passed in 10.44s

Three of the four failures are in this module. The gate bites.

## Notes

The lesson generalises beyond these two renderers: an assertion that output is not one specific wrong value does not establish it is the right value. Every assertion added in this Phase names what the output must BE.
