---
tags:
  - '#exec'
  - '#deadline-window-revision-authority'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:ae3b4c3b5a570851e574e506bb26db6b57ea5b2480562e47c93260f4650eab30'
step_id: 'S23'
related:
  - "[[2026-08-24-deadline-window-revision-authority-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace deadline-window-revision-authority with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S23 and 2026-08-24-deadline-window-revision-authority-plan placeholders are machine-filled by
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
     The Extend resolve_filing_window with optional ResultDisposition and official tipo-code context using one exact matcher and ambiguity refusal and ## Scope

- `src/cadrumo/domain/deadlines/_plazo.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Extend resolve_filing_window with optional ResultDisposition and official tipo-code context using one exact matcher and ambiguity refusal

## Scope

- `src/cadrumo/domain/deadlines/_plazo.py`

## Description

- Discover resolver and matcher implementations with Vaultspec RAG before editing.
- Extend `resolve_filing_window` with optional canonical resultado and official-code context.
- Reuse the registry's atomic semantic-coordinate projection for wildcard and exact matching.
- Refuse multiple matches with `DeadlineValidationError` and reserve `None` for zero matches.
- Add isolated, bite-capable resolution tests without mocks or parallel code vocabularies.

## Outcome

`resolve_filing_window` remains the single public filing-window resolver and now
supports post-calculation qualifier context. The implementation delegates match
semantics to `deadline_semantic_coordinate` and
`deadline_window_semantic_coordinates`; it defines no second resolver, matcher,
period parser, enum, or tipo-code map. A deferred public-facade import preserves
the existing registry/deadline initialization boundary.

Focused Ruff and six resolver tests pass, including planted malformed-context
refusals at the public boundary. The adjacent overview delegation suite
collects successfully and passes seven non-registry cases; four bundled-authority
cases remain blocked by concurrent, pre-existing incomplete deadline evidence for
Modelo 303 revision 2023 and Modelo 322 revision 2008-2022.

## Notes

The first integration run detected a circular import when the public registry
facade was imported at deadline-module initialization. Moving that same facade
import to resolution time removed the cycle without importing private registry
modules. No data was changed or lost.
