---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:b2ab725655029921cbd528e7aede0d6346559b6e712ad82d00f1d998f2414535'
step_id: 'S26'
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
     The S26 and 2026-08-03-canonical-storage-management-plan placeholders are machine-filled by
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
     The Correct WINDOWS_WORST_CASE_OBJECT_PATH_SUFFIX_LENGTH to 155 by including the missing outbound namespace segment (ledger_transaction, a real BucketEventObjectType value with no enforced length cap), fix the anti-tautology guard in test_paths.py to recompute the namespace-inclusive shape with a positive control proving it catches the dropped segment, and correct the docstring's citation of the superseded _namespace_registry module to STORAGE_NAMESPACE_REGISTRY and ## Scope

- `src/cadrumo/core/paths.py`
- `src/cadrumo/core/tests/test_paths.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Correct WINDOWS_WORST_CASE_OBJECT_PATH_SUFFIX_LENGTH to 155 by including the missing outbound namespace segment (ledger_transaction, a real BucketEventObjectType value with no enforced length cap), fix the anti-tautology guard in test_paths.py to recompute the namespace-inclusive shape with a positive control proving it catches the dropped segment, and correct the docstring's citation of the superseded _namespace_registry module to STORAGE_NAMESPACE_REGISTRY

## Scope

- `src/cadrumo/core/paths.py`
- `src/cadrumo/core/tests/test_paths.py`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

## Outcome

Landed in `531db72902` ("fix(core): correct the Windows worst-case path suffix to include the outbound namespace (S26)"), confirmed at HEAD. `WINDOWS_WORST_CASE_OBJECT_PATH_SUFFIX_LENGTH` in `src/cadrumo/core/paths.py:131-141` is now `len(...)` over a literal that includes `"ledger_transaction"` (the longest real `BucketEventObjectType` value, no enforced length cap) between the bucket and blob segments — 155 characters, not the prior 136. The anti-tautology guard landed as two tests in `test_paths.py`: `test_windows_worst_case_suffix_covers_the_real_bucket_layout_shape` (line 259) and `test_windows_worst_case_suffix_guard_catches_a_dropped_namespace_segment` (line 309, the positive control proving the guard reds when the namespace segment is dropped). The docstring's stale citation of `_namespace_registry` is corrected to `STORAGE_NAMESPACE_REGISTRY` (`paths.py:106`).

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->
