---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:d75a3290863951ecfa3d612325fc8c8445d84b17c57f9a49d00a0236908804c6'
step_id: 'S177'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Sol Medium make a catalogue key co-land with the code that consumes it, since every shipped locale gate is a state comparison rather than a change comparison and therefore cannot see the moment a key is orphaned or a call site left uncatalogued, catching drift only after it lands, which is how two unrelated single commits each silently orphaned keys and created missing ones in the same move

## Scope

- `dev/locales/ and .pre-commit-config.yaml`

## Description


## Outcome

## Notes

