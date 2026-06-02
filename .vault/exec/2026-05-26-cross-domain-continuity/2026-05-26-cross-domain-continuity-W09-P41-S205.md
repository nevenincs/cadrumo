---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-06-02'
step_id: 'S205'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cross-domain-continuity with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.
     step_id is the originating Step's canonical identifier, e.g. S01.

     Related: use wiki-links as '[[YYYY-MM-DD-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add frontmatter fields
     outside the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path. -->

# consolidate UserProfileLifecycleRepository.__init__ and UserProfileSnapshotRepository.__init__ identical signatures into shared base class or factory

## Scope

- `Wave-1 drift sweep DUPLICATE finding`
- `src/aeat/application/user_profile/_repository.py`

## Description

Introduced `_BucketBoundRepository` base class in
`src/aeat/application/user_profile/_repository.py` that holds the
shared bucket-binding `__init__` logic. Both
`UserProfileLifecycleRepository` and
`UserProfileSnapshotRepository` now inherit from it; their
identical `__init__` bodies are deleted (the inherited one
validates `bucket_id`, raises `BucketValidationError` on blank, and
either accepts an injected `SecureObjectRepository` or builds one
via `_secure_objects_for_bucket`).

## Outcome

Real refactor. 14 repository tests
(`test_repository.py` 10 + `test_repository_anti_tautology.py` 1 +
`test_repository_roundtrip.py` 3) continue to pass after the
hoist. No behaviour change; the `bucket_id` / `objects` contract
is unchanged.

## Notes

W09-P41 Wave-1 drift sweep DUPLICATE finding closed.
