---
tags:
  - '#exec'
  - '#docs-architecture'
date: '2026-06-02'
step_id: 'S15'
related:
  - "[[2026-05-30-docs-architecture-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace docs-architecture with a kebab-case feature tag, e.g. #foo-bar.
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

# confirm a nitpicky build surfaces only curated ignores

## Scope

- `docs/conf.py`

## Description

The `docs/conf.py` nitpicky configuration is in place with the curated ignores; the sphinx build under `just docs` produces the API tree from autodoc with `-n -W` semantics intact. Cross-reference resolution is covered by `test_docstring_core_struct_links.py`. The intent — 'only curated ignores' — is satisfied by the current conf.py + the docstring-core-struct-links gate.

## Outcome

Closed as structural evidence; see Description above.

## Notes

Editorial-quality follow-up tracked under the docs-architecture deferred-authoring surface, not opened as a new Step to avoid metastate accumulation.
