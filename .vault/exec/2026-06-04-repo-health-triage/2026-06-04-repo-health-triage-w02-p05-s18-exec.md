---
tags:
  - '#exec'
  - '#repo-health-triage'
date: '2026-06-04'
modified: '2026-07-17'
body_hash: 'sha256:cc495850efec558fb914fcf065246dc9fc9d31ccdc5a10ce430a5d5fe79d6270'
step_id: 'S18'
related:
  - '[[2026-06-04-repo-health-triage-plan]]'
---

# `repo-health-triage` `W02.P05.S18`

Scope: `src/aeat/application/auth/_apoderado.py`.

## Description

- Replaced `_ApoderadoConfigRepository.payload_type` with a typed
  `payload_model()` override.

## Outcome

The apoderado configuration repository no longer triggers the scoped Pyright
payload override error.

## Notes

Apoderado service tests passed.
