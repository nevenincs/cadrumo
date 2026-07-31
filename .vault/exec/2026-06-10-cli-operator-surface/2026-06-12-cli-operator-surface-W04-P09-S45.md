---
tags:
  - '#exec'
  - '#cli-operator-surface'
date: '2026-06-12'
modified: '2026-07-17'
body_hash: 'sha256:710918b0fb97bd10fcb5e5e62f81c913ae8b01f9cb927a2994f15c72cbf66d5f'
step_id: 'S45'
related:
  - '[[2026-06-10-cli-operator-surface-plan]]'
---

# W04.P09.S45 M036 Application Read-Back Surface

Scope: verify the M036 lifecycle application read-back surface.

## Description

- Verified `list_m036_declarations` and `read_m036_declaration` exist in the M036 lifecycle application module.
- Ran real-runtime M036 read-back tests against recorded declarations.

## Outcome

S45 is closed. M036 declaration reads go through the owning declaration repository surface.

## Notes

- Checks run: `pytest src/aeat/application/modelo/tests/test_m036_lifecycle_read_back.py`.
