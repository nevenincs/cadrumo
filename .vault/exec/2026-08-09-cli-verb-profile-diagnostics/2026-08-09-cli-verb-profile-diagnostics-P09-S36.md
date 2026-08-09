---
tags:
  - '#exec'
  - '#cli-verb-profile-diagnostics'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:d3beac60c2a7d7c83e2b3b3376f0cf27b712968f8ba018d974afce0d496bca39'
step_id: 'S36'
related:
  - "[[2026-08-09-cli-verb-profile-diagnostics-plan]]"
---
# Add real tests asserting both live-auth refusals name the field by operator label and carry no raw dotted path

## Scope

- `src/cadrumo/application/auth/tests/test_session_identity_refusal_grounding.py`

## Description

- Added an anchor test asserting the field's label differs from both its dotted path and its selector token.
- Added tests asserting the rendered requirement carries the label and neither raw identifier.

## Outcome

Both refusals are covered against the real committed schema, through the single helper they share.

The anchor checks three-way distinctness for the same reason as the wizard module: these two refusals named the PATH while the wizard one named the TOKEN, and a suite asserting only the absence of one form would pass against code emitting the other. Checking both makes the assertion independent of which spelling a given site happened to use.

## Verification

    uv run --no-sync pytest src/cadrumo/application/auth/tests/test_session_identity_refusal_grounding.py -n 0 -q
    3 passed in 2.64s

    uv run --no-sync pytest src/cadrumo/application/auth -m "unit or integration" -n 0 -q
    310 passed in 74.83s (0:01:14)

## Notes

The tests reach a private symbol inside their own package, which the import boundaries permit; nothing here reaches across a package boundary.
