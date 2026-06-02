---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-06-02'
step_id: 'S164'
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

# delete dead alias _profile_binding_selectors

## Scope

- `src/aeat/domain/user_profile/_registry_contract.py`

## Description

Removed the dead alias `_profile_binding_selectors = profile_binding_selectors` from `src/aeat/domain/user_profile/_registry_contract.py:308`. The only external reference (`test_profile_binding_selectors_is_public...` in test_registry_contract.py) is a test function name that happens to share the prefix; not an actual import of the alias. All 4 tests in test_registry_contract.py continue to pass after removal.

## Outcome

Closed by direct code edit; see Description above.

## Notes

Real cleanup, not audit-based — duplicate registrations were live in the registry and the alias was unused.
