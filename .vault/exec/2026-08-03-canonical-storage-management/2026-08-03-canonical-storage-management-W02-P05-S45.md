---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:5a441e98365436b56c5269dcf3a2ac007881071ca3b94234bfc08427a0ecbe2c'
step_id: 'S45'
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
     The S45 and 2026-08-03-canonical-storage-management-plan placeholders are machine-filled by
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
     The Declare the registry disk-cache resolver's pytest-shared temporary branch as an explicit test-pinned exception on the member rather than an undeclared special case, gated by a test asserting the declaration exists and the branch still selects under pytest and ## Scope

- `src/cadrumo/domain/calculations/registry/_loader_cache.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Declare the registry disk-cache resolver's pytest-shared temporary branch as an explicit test-pinned exception on the member rather than an undeclared special case, gated by a test asserting the declaration exists and the branch still selects under pytest

## Scope

- `src/cadrumo/domain/calculations/registry/_loader_cache.py`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

## Outcome

Landed in `28179b95dc`, confirmed at HEAD. `REGISTRY_DISK_CACHE`'s declaration in `src/cadrumo/core/_storage_taxonomy_locations.py:343-358` carries an explicit `test_pinned_exception` field describing exactly the pytest-shared-directory branch (`domain/calculations/registry/_loader_cache.py`'s `_running_under_pytest()` check at line 156). Gated by `domain/calculations/registry/tests/test_registry_disk_cache_location.py`, which asserts both the declaration exists and the branch still selects the shared directory under pytest.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->
