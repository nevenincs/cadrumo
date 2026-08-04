---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:4f07e57214f03edf1a82a540392ab129ccd120d4c3c8efbdbdd7732af4d78b7e'
step_id: 'S51'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Re-point the corpus-text cache read onto the accessor, gated by the existing corpus-text cache location test re-expressed against the taxonomy

## Scope

- `src/cadrumo/domain/calculations/registry/_validate_evidence.py`

## Description

## Outcome

Landed in `06eb40877b`, confirmed at HEAD. `src/cadrumo/domain/calculations/registry/_validate_evidence.py:147` returns `storage_path(StorageCategory.CORPUS_TEXT_CACHE) / _CORPUS_TEXT_CACHE_FILENAME` rather than reading `cadrumo_corpus_text_cache_dir` directly. Gated by `domain/calculations/registry/tests/test_corpus_text_cache_location.py`.

## Notes
