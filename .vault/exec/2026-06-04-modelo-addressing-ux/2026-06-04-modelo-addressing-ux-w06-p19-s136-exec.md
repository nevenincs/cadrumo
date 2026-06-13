---
tags:
  - '#exec'
  - '#modelo-addressing-ux'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S136'
related:
  - '[[2026-06-04-modelo-addressing-ux-plan]]'
---

# W06.P19.S136 backend revision selector defaulting extraction

Scope:
- `src/aeat/application/modelo`

## Description

- Add application-level `ModeloWorkAddress` and address resolution services.
- Move calculation revision addressing defaults for verify file and export out of CLI selector helpers.
- Export the address services from the application modelo package.
- Update `_modelo.py` to consume application-level address services instead of private selector functions.

## Outcome

Implemented:

- `src/aeat/application/modelo/_work_addressing.py`
- `src/aeat/application/modelo/__init__.py`
- `src/aeat/entrypoints/cli/_modelo.py`

The backend now owns:

- exact or natural work-unit address resolution;
- exact or selected calculation-revision resolution;
- command-specific `verify`, `file`, and `export` defaults;
- exportable revision defaulting through filed pointer then current verified revision.

Verification:

- `uv run python -m py_compile src/aeat/application/modelo/_work_addressing.py src/aeat/application/modelo/__init__.py src/aeat/entrypoints/cli/_modelo.py src/aeat/entrypoints/cli/_modelo_payloads.py`
- `uv run pytest src/aeat/application/modelo/test_selectors.py src/aeat/application/modelo/test_export.py -q`

## Notes

- Focused CLI natural-key/export tests timed out at 120 seconds and remain covered by later W05/W06 verification gates.
