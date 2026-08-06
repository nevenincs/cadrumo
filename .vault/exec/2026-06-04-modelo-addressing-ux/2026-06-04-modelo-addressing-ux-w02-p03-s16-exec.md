---
tags: ['#exec', '#modelo-addressing-ux']
date: '2026-06-04'
modified: '2026-07-17'
body_hash: 'sha256:5ea04f3c4f7a783504068fb9f949943c9f5eab4aa3c23a1b9f361f56b09f538b'
step_id: 'S16'
related:
  - '[[2026-06-04-modelo-addressing-ux-plan]]'
---

# W02.P03.S16 natural-key work status

Scope:
- `src/aeat/entrypoints/cli/_modelo.py`
- `src/aeat/entrypoints/cli/test_modelo_work_ux.py`

## Description

- Add `--modelo`, `--year`, `--period`, `--revision`, and `--bucket-id` resolution to `modelo work status`.
- Route exact and natural addressing through the shared work selector helper.

## Outcome

Operators can inspect a work unit by visible filing target without copying the raw `work_unit_id`; exact ids remain accepted.

## Notes

- Real CLI coverage verifies status resolution by modelo/year/period.
