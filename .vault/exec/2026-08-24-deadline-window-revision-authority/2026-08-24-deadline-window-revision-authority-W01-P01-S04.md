---
tags:
  - '#exec'
  - '#deadline-window-revision-authority'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:a5d0aa6870eb279bd2e43cc74c1e38bca89f995568c0602a507d9964b69bbf33'
step_id: 'S04'
related:
  - "[[2026-08-24-deadline-window-revision-authority-plan]]"
---
# Extend deadline-window loading and serialization for typed qualifiers while preserving unqualified rows and fragmented authoring ownership

## Scope

- `src/cadrumo/domain/calculations/registry/_loader.py`
- `src/cadrumo/domain/calculations/registry/tests/`

## Description

- Compile qualified deadline-window TOML through the shared `ResultDisposition` authority.
- Preserve the exact frozen object for every unqualified deadline-window row.
- Refuse qualifier declarations outside nested `deadline_windows` rows.
- Prove single-file and fragmented layouts hydrate to the same frozen modelo definition.

## Outcome

Deadline qualifier authoring now flows through the existing revision compiler and
fragment ownership rules. Qualified rows retain typed resultado and official-code
scope, while the legacy unqualified corpus takes the unchanged compiler path.

## Notes

Focused deadline-loader, qualifier-schema, and directory-loader tests passed. Ruff
reported no findings on the changed Python surface. No data was changed.
