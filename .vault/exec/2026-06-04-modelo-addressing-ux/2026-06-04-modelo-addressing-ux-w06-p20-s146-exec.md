---
tags:
  - '#exec'
  - '#modelo-addressing-ux'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S146'
related:
  - '[[2026-06-04-modelo-addressing-ux-plan]]'
---

# W06.P20.S146 Extracted-module regression coverage

Scope:
- `src/aeat/entrypoints/cli/test_work_resume.py`
- `src/aeat/entrypoints/cli/test_modelo_work_preview_maritime_exemption.py`
- `src/aeat/entrypoints/cli/test_modelo_work_natural_key.py`
- `src/aeat/entrypoints/cli/test_architecture_boundaries.py`
- `src/aeat/entrypoints/cli/test_cli_module_size.py`

## Description

- Run real CLI behavior tests over the extracted workflow-run commands.
- Run real CLI behavior tests over the extracted maritime preview command and application service path.
- Run natural-key work addressing tests to confirm shared helper imports did not regress common model/year/period addressing.
- Run the new static architecture and size guards.

## Outcome

- `work runs` and `work resume` remain wired under `aeat app modelo work`.
- `work preview-maritime-exemption` still validates localized help, JSON payloads, RETMAR warning behavior, DA41 refusal propagation, and active-profile fact resolution.
- Natural-key work addressing still passes after helper extraction.
- Static W06 guards execute with the focused CLI gate.

## Notes

- Test warnings are limited to the existing Click `protected_args` deprecation.

Verification:
- `.venv\Scripts\pytest.exe src/aeat/entrypoints/cli/test_architecture_boundaries.py src/aeat/entrypoints/cli/test_cli_module_size.py src/aeat/entrypoints/cli/test_work_resume.py src/aeat/entrypoints/cli/test_modelo_work_preview_maritime_exemption.py src/aeat/entrypoints/cli/test_modelo_work_natural_key.py -q` - 25 passed.
