---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-30'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:4494982a0a51b5f3e48a0137d835f0db9f2baa3acc3e0d3ad5f90b56b091835b'
step_id: 'S354'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Rename the workspace schema record's section_path, which collides with an established field of the same name and type carrying a different meaning. Verified: the workspace projection HARDCODES a record-family label at six sites -- casillas twice, then bindings, formulas, relations and parameters -- while the calc-sheets layout module DERIVES section_path from the casilla's own declared section at two sites. Same name, same type, one a record-family label and the other the modelo's declared structure. This is the same collision class as the cli_path family already documented. Cheap to rename before the C2 destinations consume it, expensive after

## Scope

- `src/cadrumo/application/modelo/workspace.py`
- `workspace_models.py`
- `and src/cadrumo/application/storage/calc_sheets/_layout.py as the colliding reference`

## Changes

- `M` `src/cadrumo/application/modelo/workspace_models.py`
- `M` `src/cadrumo/application/modelo/workspace.py`
- `M` `src/cadrumo/application/modelo/tests/test_workspace_models.py`
- `M` `src/cadrumo/entrypoints/tui/modelo/view/inputs.py`
- `M` `src/cadrumo/entrypoints/tui/modelo/view/models.py`
- `verify:` `pytest test_workspace_models.py + entrypoints/tui/modelo` -> `152 passed`
- `verify:` `ruff check` -> `every touched file equals its HEAD baseline`

## Notes

`ModeloWorkspaceSchemaRecordV1.section_path` -> `record_family`, and its bound
`_MAX_SCHEMA_SECTION_DEPTH` -> `_MAX_SCHEMA_RECORD_FAMILY_DEPTH` (used by that
field alone). `section_path` now means one thing tree-wide: the modelo's
declared structure, as `calc_sheets/_layout.py` and `application/modelo/
work_review.py` already used it. `view/work_review.py:589` still reads
`row.section_path` and correctly refers to that real-structure field.

The collision had already produced two FALSE docstrings, which is the concrete
cost rather than a stylistic one: `_section_title` claimed to render a
"registry-declared section path", and `ModeloWorkspaceSectionV1` claimed "the
path is the registry's own section_path". Both described a field holding a
record-family label, so a reader trusting either would look for section
structure the projection does not carry at all. Both corrected. A fifteen-line
docstring in `inputs.py` existing only to warn readers about the collision is
now eight, the warning being obsolete.

NOT taken: `ModeloWorkspaceSectionV1` is still named for a section while
holding a family label. Renaming a type is wider than this row, and W03.P20.S355
projects the modelo's REAL section structure into this facet -- that row should
settle both names once the two concepts coexist.
