---
tags:
  - '#exec'
  - '#casilla-schema'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:edda0045c0a17429d92029a69c066fd5dc55d799d42bb93217a66aa36e7a8d6e'
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
