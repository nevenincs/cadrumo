---
tags:
  - '#exec'
  - '#casilla-schema'
date: '2026-08-11'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:7bc8226c9aabbfdb27333706fb3d594a4c547ac2a1693932ff9d1449d40c054e'
step_id: 'S15'
related:
  - "[[2026-08-10-casilla-schema-plan]]"
---
# Classify official boxes through one registry authority

## Scope

- `src/cadrumo/domain/calculations/registry/_export.py`
- `src/cadrumo/domain/calculations/registry/__init__.py`
- `src/cadrumo/domain/calculations/registry/tests/test_official_box_classification.py`

## Description

- Add the sole facade-exported `classify_official_boxes` derivation and return one `OfficialBoxStatus` for every revision casilla.
- Resolve binding-record fields before measuring fixed-width direct and row mappings, explicit binding-field representation, and official XML dictionary entries.
- Require validated source-root and source-catalogue authority for XML dictionaries; classify layout-less and otherwise unrepresented casillas as `UNDEFINED`.

## Outcome

- Real bundled M720, M100 2024, M349, and M130 regressions exercise all three states and the XML authority refusal.
- The M349 regression proves a row-derived official box with no `export_refs` is still `ADDRESSED`.
- Five focused tests pass; Ruff, format, BasedPyright, facade identity, sole-declaration, and diff gates are green.
- Formal review initially found the derive-before-scan proof was not load-bearing. The corrected M720 test reads the real pre-snapshot authoring revision with empty binding-record fields; bypassing only classifier derivation now fails and the restored implementation passes. Formal re-review reports PASS.

## Notes

- The classifier answers official slot declaration only. It does not decide producer ownership, value arrival, applicability, or completeness.
- The bite proof temporarily replaced the classifier's derived-layout iteration with raw layouts, observed the M720 state degrade from `REPRESENTED_VIA_BINDING` to `UNDEFINED`, and restored the exact production call in the same session.
- This step was executed twice in parallel on diverged history. The second execution reached the same derivation and additionally proved fail-closed behaviour when required XML dictionary evidence cannot be resolved or parsed, and exercised Modelo 100 2025 alongside 2024. Reconciling the two, this lane's implementation is canonical and carries the Spanish-stem name `clasificar_casillas_oficiales`; the parallel English-named `classify_official_boxes` and its duplicate test were deleted after confirming equivalent coverage. Plan rows `W04.P07.S52` and `W04.P07.S62` in the export-fragment plan were repointed to the Spanish name, which they must import rather than re-union export mechanisms.
