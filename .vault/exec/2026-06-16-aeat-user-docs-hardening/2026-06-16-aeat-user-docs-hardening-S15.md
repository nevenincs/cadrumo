---
tags:
  - '#exec'
  - '#aeat-user-docs-hardening'
date: '2026-07-04'
modified: '2026-07-04'
step_id: 'S15'
related:
  - "[[2026-06-16-aeat-user-docs-hardening-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace aeat-user-docs-hardening with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S15 and 2026-06-16-aeat-user-docs-hardening-plan placeholders are machine-filled by
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
     The Harden index.md and ## Scope

- `docs/how-to/index.md` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Harden index.md

## Scope

- `docs/how-to/index.md`

## Description

- Verify-close: read `index.md` (the how-to landing/router page) against the hardening standard and confirm resolution at HEAD.
- Confirm the page is a question-first task router ("Pick the question closest to what you are trying to do") that links each how-to guide with imperative task labels; no first-person-plural, gerund-header, or self-praise anti-patterns.
- Confirm every linked how-to target resolves (relative markdown links) and the taxonomy matches the guides in the tree.

## Outcome

- Page verified compliant at HEAD. Delta: none required. CLI conformance gate green (the router carries no commands of its own).

## Notes

- Router-only page; its correctness is link integrity + task-label clarity, both sound.
