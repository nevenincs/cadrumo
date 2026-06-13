---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S117'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W02.P10.S117 Config Custody Registrar Extraction

Scope: `W02.P10.S117` extracted the selected residual config CLI group into a focused transport registrar module.

## Description

- Add `src/aeat/entrypoints/cli/_config/_custody.py` with root custody command registration.
- Move lock, unlock, rekey, recover, show-recovery, verify-recovery transport wiring behind `register_custody_commands`.
- Keep profile selection delegated to application-owned profile lifecycle services.
- Wire the config root through the custody registrar and reuse the shared profile pointer selector for profile switch.

## Outcome

The config root now delegates custody commands to `_custody.py` while preserving command names, payload schemas, and backend service calls.

## Notes

No schema or application custody policy was changed.
