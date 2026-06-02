---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-06-02'
step_id: 'S19'
related:
  - "[[2026-06-02-registry-hardening-next-work-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace schema-hardening with a kebab-case feature tag, e.g. #foo-bar.
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

# Assess loader fragment compiler extraction boundaries

## Scope

- `src/aeat/domain/calculations/registry/_loader.py`

## Description

- Inspect current `_loader.py` diff before touching any loader code.
- Enumerate loader classes, public functions, fragment merge helpers,
  catalogue loaders, source discovery helpers, and cache fingerprint helpers.
- Record the fragment-compiler extraction boundary in a vault audit.
- Leave `_loader.py` untouched because it carries peer formatting WIP.

## Outcome

- Fragment compiler extraction boundary identified: manifest/revision fragment
  merge helpers can move behind a private helper module without changing public
  loader semantics.
- Public loader spine, catalogue loading, source discovery, and cache
  fingerprinting should remain in `_loader.py` for now.
- Vault body-link, frontmatter, and plan checks passed.
- `P04.S19` is complete.

## Notes

- `_loader.py` is dirty in the shared worktree with formatting-only changes.
  This slice did not stage or edit that file.
