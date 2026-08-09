---
tags:
  - '#exec'
  - '#cli-verb-profile-diagnostics'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:bb06a049d38783c2b6dd07c541117c0f729a48fddedff7ba4026457e53e38864'
step_id: 'S33'
related:
  - "[[2026-08-09-cli-verb-profile-diagnostics-plan]]"
---
# Name the cleared profile identity field by its schema-derived label in the live-auth identity-cleared refusal

## Scope

- `src/cadrumo/application/auth/_sessions.py`

## Description

- Added `_grounded_profile_identity_requirement`, rendering the profile tax-identifier field through the canonical requirement builder and shared formatter.
- Passed it on the identity-cleared refusal's context and removed the dotted path from the sentence.

## Outcome

An operator whose profile identity has been cleared is told which field to restore, named as the profile editor names it.

The refusal CONDITION is untouched, including its deliberate early return for a profile that is absent or still in setup. That branch exists so an operator with no profile is not told to restore a field on it, and it is preserved exactly.

## Verification

    uv run --no-sync pytest src/cadrumo/application/auth -m "unit or integration" -n 0 -q
    310 passed in 74.83s (0:01:14)

## Notes

Found by the closing locale-catalogue sweep, not by the earlier passes. This surface was outside both the CLI tree and every site list this work had been given.
