---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:b2def063fb698be14b456fb2d71b6fbe863d8b615373eaf5eaac5ca192eee18b'
step_id: 'S100'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace canonical-storage-management with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S100 and 2026-08-03-canonical-storage-management-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Converge the five resolvers onto the new parameterised helper and delete the five standalone functions, lower priority than the other Wave 2 phases and not a closure blocker and ## Scope

- `src/cadrumo/entrypoints/cli/registry.py`
- `src/cadrumo/entrypoints/cli/_app_live.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Converge the five resolvers onto the new parameterised helper and delete the five standalone functions, lower priority than the other Wave 2 phases and not a closure blocker

## Scope

- `src/cadrumo/entrypoints/cli/registry.py`
- `src/cadrumo/entrypoints/cli/_app_live.py`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

## Outcome

Landed in the same commit as S99 (`d9145d3b83`), confirmed at HEAD. All five original standalone resolvers — the four `_resolve_*_root` functions in `registry.py` and `_resolve_live_output_root` in `_app_live.py` — are gone; `registry.py` and `_app_live.py` now call `resolve_optional_root` at every site, confirmed by a zero-hit search for `_resolve_.*_root` across both files. `_app_live.py`'s settings-default sites keep `load_settings` as a deferred function-local import, matching the file's existing lazy-import discipline. `test_storage_liveness_gate.py`'s module docstring (previously citing `_resolve_live_output_root(value, "field_name")` by name as its worked example for the string-constant evidence shape) was updated since the call now reaches its field through an attribute load; the third evidence shape itself remains supported and tested for other dynamic-name lookups.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->
