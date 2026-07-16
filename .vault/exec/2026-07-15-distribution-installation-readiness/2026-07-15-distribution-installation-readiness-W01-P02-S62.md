---
tags:
  - '#exec'
  - '#distribution-installation-readiness'
date: '2026-07-16'
modified: '2026-07-16'
step_id: 'S62'
related:
  - "[[2026-07-15-distribution-installation-readiness-plan]]"
---

# Keep master-key unlock failures non-repairable and preserve the active pointer

## Scope

- `src/cadrumo/application/workflow`

## Description

- Treat master-key provider and secret-store access failures as non-repairable profile health states.
- Replace the destructive pointer-clearing recommendation with an access-restoration action.
- Exercise the encrypted file-backed profile path with an incorrect passphrase and a confirmed repair request.

## Outcome

- A failed master-key unlock can no longer authorize pointer deletion.
- The confirmed repair remains a dry run and preserves the exact active pointer.
- Focused verification passed: Ruff, ty, and eight real-behavior profile-health tests.

## Notes

- The regression reproduces the original `MasterKeyPassphraseMismatchError` through the real encrypted repository and provider session.
