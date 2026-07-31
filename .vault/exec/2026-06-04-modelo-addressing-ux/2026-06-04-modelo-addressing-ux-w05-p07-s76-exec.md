---
tags:
  - '#exec'
  - '#modelo-addressing-ux'
date: '2026-06-04'
modified: '2026-07-17'
body_hash: 'sha256:9773b1f1a093566dfb22d9400edec6c2b1dc59b91f9ea5ba7d7e5aec6bd41c40'
step_id: 'S76'
related:
  - '[[2026-06-04-modelo-addressing-ux-plan]]'
---

# `W05.P07.S76` focused modelo CLI gate

Step scope: `src/aeat/entrypoints/cli`.

## Description

- Run the focused CLI tests for natural-key modelo work lifecycle behavior.
- Include legacy exact-ID compatibility and ID-type hint coverage.
- Include modelo export and projection compatibility coverage for adjacent command behavior.

## Outcome

Focused CLI verification passed:

- `src/aeat/entrypoints/cli/test_modelo_work_ux.py`
- `src/aeat/entrypoints/cli/test_modelo_work_natural_key.py`
- `src/aeat/entrypoints/cli/test_modelo_export_verb.py`
- `src/aeat/entrypoints/cli/test_modelo_work_id_type_hint.py`
- `src/aeat/entrypoints/cli/test_modelo_projection.py`

Result: 39 passed.

## Notes

The run emitted existing Click `protected_args` deprecation warnings from the CLI harness. No test failures were observed.
