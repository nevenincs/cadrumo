---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:4c0ab1a581c3a4fd3ad104bc66afcf7dd68499140454f365c5170953ba41d9b7'
step_id: 'S42'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Add a corpus-search category member and its settings field, delete the module-local index subdirectory constant and the local parent-mkdir workaround, gated by a test asserting the per-field environment override now resolves and the tree materialiser pre-creates it

## Scope

- `src/cadrumo/application/corpus_search/_runtime.py`

## Description

- Add a corpus-search taxonomy category member and settings field.
- Delete the module-local index-subdirectory constant and the local parent-mkdir workaround.

## Outcome

Landed in commit `b062897f8e` ("retire the last module-local storage locations"). `StorageCategory.CORPUS_SEARCH_CACHE` declared (`subpath="cache/corpus-search"`, `consumer_module="application/corpus_search/_runtime.py"`, `settings_field="cadrumo_corpus_search_cache_dir"`); `Settings.cadrumo_corpus_search_cache_dir` added to `core/config.py`. `_runtime.py`'s `_INDEX_SUBDIR` module-local constant and its `database_path.parent.mkdir(parents=True, exist_ok=True)` workaround are both confirmed deleted; `corpus_search_dir()` now reads `resolved.cadrumo_corpus_search_cache_dir` directly. Gated by `test_output_dir_state_root.py`'s `DERIVED_OUTPUT_SUBPATHS` oracle, asserting the field resolves correctly under an environment-overridden storage root, and enrolled `EXCLUDED` in the fingerprint-participation gate as a regenerable cache. The tree materialiser pre-creates it as an ordinary derived member (no `derives_settings_default=False` override).

## Notes

This record was missing even though the plan already showed the Step `checked: true` — confirmed the checkbox was accurate and only the exec record document was absent, not the underlying work. No unchecking needed.
