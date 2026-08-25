---
tags:
  - '#exec'
  - '#deadline-window-revision-authority'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:cf2988a3c8f02f901cb938db67fbce3783d33f12830983bb043027b9656a7a8b'
step_id: 'S49'
related:
  - "[[2026-08-24-deadline-window-revision-authority-plan]]"
---

# Restore canonical formatting after the concurrent authority-reset fix landed unformatted on the registry authority and its native-capture proof, preserving reset linearization behavior

## Scope

- `src/cadrumo/domain/calculations/registry/_authority.py`
- `src/cadrumo/domain/calculations/registry/tests/test_authority_native_capture.py`

## Description

- Apply the repository-owned formatter after the concurrent authority-reset linearization landed.
- Preserve the reset barrier, authority generation, deadline projection, assertion operands, and AST symbol checks.
- Re-run native-capture, deadline projection, and ownership tests and obtain independent review.

## Outcome

Ruff check and format checks pass. The native-capture, canonical deadline projection, and deadline ownership suite passes 20 tests. Independent review approved with zero findings and confirmed reset linearization and deadline authority behavior are unchanged.

## Notes

The textual diff only wraps one membership assertion and one AST-comprehension condition in the native-capture proof. The authority file is status-marked solely by line-ending normalization and has no textual or word diff. Git reports an informational CRLF-to-LF warning.
