---
tags:
  - '#exec'
  - '#arch-remediation-registry-format'
date: '2026-07-03'
modified: '2026-07-03'
step_id: 'S15'
related:
  - "[[2026-07-02-arch-remediation-registry-format-plan]]"
---




# Add a loud loader refusal that raises a load error naming the fragmented layout when an inline bindings or formulas table appears in revision.toml

## Scope

- `src/aeat/domain/calculations/registry/_loader.py`

## Description

- Add the loud loader refusal for an inline section table in revision.toml.

## Outcome

Done in `e99a3a9ad3`: `_merge_revision_manifest` raises RegistryLoadError naming the '<section>/' fragment subdirectory when a section field appears inline. Verified by injecting `[[revisions.X.bindings]]` into a migrated revision.toml — the loader refuses with the layout-naming error.

## Notes

Verified live at HEAD (injection test).
