---
tags:
  - '#exec'
  - '#casilla-schema'
date: '2026-08-11'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:0852c5336e620b8f4a74f84adc3f702e6542e4ed8fdc52d7a24c53f784efb08e'
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
- The type reports declaration status only; it does not own producer selection, value arrival, applicability, or completeness.
- This step was executed twice in parallel on diverged history. The second execution declared the same three-state vocabulary and proved the same properties, reaching the identical member set. Reconciling the two, the enum declared here is canonical and was subsequently renamed to `EstadoCasillaOficial` (`src/cadrumo/core/_estado_casilla_oficial.py`) under the Spanish-stem naming rule; the parallel English-named module and its test were deleted as duplicates after confirming member-for-member equivalence and that this lane's test is a strict superset, carrying the retired-family absence scan the duplicate lacked.
