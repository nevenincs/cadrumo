---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:ab5b62f73a858c10e33bb583f0c734e01e62176330a58a00f450a1de629608a8'
step_id: 'S52'
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
     The S52 and 2026-08-03-canonical-storage-management-plan placeholders are machine-filled by
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
     The Re-point the validation-verdict cache read onto the accessor, gated by the existing verdict location test re-expressed against the taxonomy and ## Scope

- `src/cadrumo/domain/calculations/registry/_validate_verdict.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Re-point the validation-verdict cache read onto the accessor, gated by the existing verdict location test re-expressed against the taxonomy

## Scope

- `src/cadrumo/domain/calculations/registry/_validate_verdict.py`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

## Outcome

Landed in `06eb40877b`, confirmed at HEAD. `src/cadrumo/domain/calculations/registry/_validate_verdict.py:174` returns `storage_path(StorageCategory.VALIDATION_VERDICT_CACHE) / f"..."` rather than reading `cadrumo_validation_verdict_cache_dir` directly. Gated by `domain/calculations/registry/tests/test_validation_verdict_location.py`.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->
