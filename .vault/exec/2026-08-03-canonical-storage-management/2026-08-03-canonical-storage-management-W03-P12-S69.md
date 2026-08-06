---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:9bca6910b976838a46e55103c0f711206a0870f2bf6d737070ecb4d6117394af'
step_id: 'S69'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Add the materialisation-parity gate asserting the tree ensure_storage_tree builds on disk is exactly the declared taxonomy member set in both directions, with the file-versus-directory leaf case asserted separately and idempotency proven by a second call that must preserve content

## Scope

- `src/cadrumo/tests/test_storage_materialisation_parity.py`

## Description

- Add the gate asserting the tree `ensure_storage_tree` builds on disk is exactly the declared taxonomy member set, in both directions (nothing declared is missing, nothing on disk is unexplained).
- Assert the file-versus-directory leaf case separately.
- Prove idempotency: a second call preserves existing content rather than remove-and-recreate.

## Outcome

Landed in commit `0d4bb71997` (ADR R9's first supporting gate).

## Notes

This record and the plan Step's own scope originally cited the wrong path, `src/cadrumo/tests/test_storage_materialisation_parity.py` — the real file is `src/cadrumo/core/tests/test_storage_materialisation_parity.py` (under `core/tests/`). Found on a fresh-context honesty review and corrected here and in the plan Step scope; the Description/Outcome content above was otherwise accurate.
