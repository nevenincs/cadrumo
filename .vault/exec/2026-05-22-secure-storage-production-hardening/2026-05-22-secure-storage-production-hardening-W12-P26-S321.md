---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
step_id: 'S321'
related:
  - "[[2026-05-22-secure-storage-production-hardening-refactor-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace secure-storage-production-hardening with a kebab-case feature tag, e.g. #foo-bar.
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

# W12.P26.S321 bucket event repository

## Scope

- `src/aeat/domain/buckets/_event_repository.py`

## Description

- Audited `domain.buckets._event_repository` against the target `runtime-default` (owner `W12.P21.S83`).
- Confirmed `BucketEventHistoryRepository.__init__` routes through the canonical runtime helper `secure_object_repository_for_active_bucket` when no `objects=` override is passed; no parallel constructor path opens its own SecureObjectRepository.
- Confirmed the `secure-object`, `runtime`, and `active-profile` signals are all accounted for by this single delegation: the runtime helper resolves the active-profile bucket id and constructs a `SecureObjectRepository` bound to it, so every event read / write is automatically bucket-scoped against the active profile.
- Confirmed the `manifest-bucket` signal is appropriate: the encrypted-SQL persistence row lives under the active bucket's manifest directory; the repository never reads or writes outside that scope.
- Persistence delegation uses the standard `SecureObjectWrite` envelope and the `save` / `update` repository API; no shadow write path, no direct SQL escape from the secure-object boundary.

## Outcome

- AFR-219 closed: the runtime-default secure-object routing is correctly delegated through the canonical helper; no source change required.
- No new tests authored — the existing bucket-event-repository roundtrip tests cover the runtime-default contract.

## Notes

- Audit-only Step; the source file is unchanged.
