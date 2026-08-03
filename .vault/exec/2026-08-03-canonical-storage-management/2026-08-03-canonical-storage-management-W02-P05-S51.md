---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:3ebc333ded4809e88ec2b6b10be2181a8a11d2119b0e75af83c866af2c5f5504'
step_id: 'S51'
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
     The S51 and 2026-08-03-canonical-storage-management-plan placeholders are machine-filled by
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
     The Re-point the corpus-text cache read onto the accessor, gated by the existing corpus-text cache location test re-expressed against the taxonomy and ## Scope

- `src/cadrumo/domain/calculations/registry/_validate_evidence.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Re-point the corpus-text cache read onto the accessor, gated by the existing corpus-text cache location test re-expressed against the taxonomy

## Scope

- `src/cadrumo/domain/calculations/registry/_validate_evidence.py`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

## Outcome

Landed in `06eb40877b`, confirmed at HEAD. `src/cadrumo/domain/calculations/registry/_validate_evidence.py:147` returns `storage_path(StorageCategory.CORPUS_TEXT_CACHE) / _CORPUS_TEXT_CACHE_FILENAME` rather than reading `cadrumo_corpus_text_cache_dir` directly. Gated by `domain/calculations/registry/tests/test_corpus_text_cache_location.py`.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->
