---
tags:
  - '#exec'
  - '#registry-authority-artifact-boundary'
date: '2026-09-14'
modified: '2026-09-14'
body_schema: 'body-v2'
body_hash: 'sha256:da6500a75f01feb8ab1782caa14632b4f3235f80005c2cb950d379e98c778cb0'
step_id: 'S27'
related:
  - "[[2026-09-14-registry-authority-artifact-boundary-plan]]"
---
# Define context-required profile create/decode factories and pure validators; preserve exact stored schema ID/version refusal without global I/O

## Scope

- `src/cadrumo/domain/user_profile/values.py`

## Changes

- `M` `src/cadrumo/domain/user_profile/values.py`
- `M` `src/cadrumo/domain/user_profile/tests/test_contextful_values.py`
- `verify:` `checkpoint B profile context selection` -> `pass`
