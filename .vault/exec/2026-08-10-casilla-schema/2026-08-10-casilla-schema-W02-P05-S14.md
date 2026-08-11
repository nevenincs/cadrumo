---
tags:
  - '#exec'
  - '#casilla-schema'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:f55426f0915872f259322ad70897ddb11032ac734138e300ca0b4d8c69fa6639'
step_id: 'S14'
related:
  - "[[2026-08-10-casilla-schema-plan]]"
---
# Add the canonical official-box status vocabulary

## Scope

- `src/cadrumo/core/_official_box_status.py`
- `src/cadrumo/core/__init__.py`
- `src/cadrumo/core/tests/test_official_box_status.py`

## Description

- Add the sole core-owned `OfficialBoxStatus` string enum with `ADDRESSED`, `REPRESENTED_VIA_BINDING`, and `UNDEFINED` states.
- Export the exact enum identity through the core facade without an alias or compatibility bridge.
- Prove exact member names, values, facade identity, and sole source declaration.

## Outcome

- The three-state vocabulary is available for the registry classifier without embedding classification behavior in core.
- One focused unit test passes; Ruff, format, BasedPyright, collection, structural, and diff gates are green.
- Formal review initially found an alias-detection gap; the test now pins exact `__members__` keys and re-review reported PASS.

## Notes

- Registry classification remains deliberately deferred to S15; this step introduces vocabulary only.
