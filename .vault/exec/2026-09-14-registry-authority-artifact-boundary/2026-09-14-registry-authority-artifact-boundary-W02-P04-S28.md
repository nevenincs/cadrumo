---
tags:
  - '#exec'
  - '#registry-authority-artifact-boundary'
date: '2026-09-14'
modified: '2026-09-14'
body_schema: 'body-v2'
body_hash: 'sha256:9de415e3a01b4f4053aa7ded98368213e6a30f9e4880cfadf754b472c820fda7'
step_id: 'S28'
related:
  - "[[2026-09-14-registry-authority-artifact-boundary-plan]]"
---
# Thread the pinned schema through record lifecycle, secure repository decoding, projections, overview and validation; remove the duplicate schema cache

## Scope

- `src/cadrumo/application/user_profile`

## Changes

- `A` `src/cadrumo/application/user_profile/authority_context.py`
- `M` `src/cadrumo/application/user_profile/projections.py`
- `M` `src/cadrumo/application/user_profile/overview.py`
- `M` `src/cadrumo/application/user_profile/validation.py`
- `verify:` `checkpoint B profile and capsule selection` -> `pass`
