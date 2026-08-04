---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:b2eb88f2baedf805b710c1474c35ce76ab748d1973c18f08857570a2638659d2'
step_id: 'S100'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Converge the five resolvers onto the new parameterised helper and delete the five standalone functions, lower priority than the other Wave 2 phases and not a closure blocker

## Scope

- `src/cadrumo/entrypoints/cli/registry.py`
- `src/cadrumo/entrypoints/cli/_app_live.py`

## Description

## Outcome

Landed in the same commit as S99 (`d9145d3b83`), confirmed at HEAD. All five original standalone resolvers — the four `_resolve_*_root` functions in `registry.py` and `_resolve_live_output_root` in `_app_live.py` — are gone; `registry.py` and `_app_live.py` now call `resolve_optional_root` at every site, confirmed by a zero-hit search for `_resolve_.*_root` across both files. `_app_live.py`'s settings-default sites keep `load_settings` as a deferred function-local import, matching the file's existing lazy-import discipline. `test_storage_liveness_gate.py`'s module docstring (previously citing `_resolve_live_output_root(value, "field_name")` by name as its worked example for the string-constant evidence shape) was updated since the call now reaches its field through an attribute load; the third evidence shape itself remains supported and tested for other dynamic-name lookups.

## Notes
