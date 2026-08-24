---
tags:
  - '#exec'
  - '#deadline-window-revision-authority'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:15dc9e590b36705c24d4b37d687eb31c6d9f7681c0875f979123dbc3e5ed362a'
step_id: 'S24'
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
     The S24 and 2026-08-24-deadline-window-revision-authority-plan placeholders are machine-filled by
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
     The Keep resolve_filing_closes_on as the unqualified convenience and route post-calculation M210 plazo through the same matcher and ## Scope

- `src/cadrumo/domain/deadlines/_plazo.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Keep resolve_filing_closes_on as the unqualified convenience and route post-calculation M210 plazo through the same matcher

## Scope

- `src/cadrumo/domain/deadlines/_plazo.py`

## Description

- Search the code and decision corpora with Vaultspec RAG for pre- and post-calculation plazo matching paths.
- Read the canonical resolver and pre-calculation work-plazo consumer in full, then confirm every resolver call site by exact-symbol search.
- Preserve `resolve_filing_closes_on` as the qualifier-free convenience over `resolve_filing_window` and document the shared-matcher boundary explicitly.
- Run focused Ruff and pytest gates across the deadline resolver and work-plazo contract.

## Outcome

The redeclaration audit found no competing M210 deadline resolver. The pre-calculation work posture calls `resolve_filing_closes_on`, which delegates directly to `resolve_filing_window`; qualified post-calculation callers can pass canonical `ResultDisposition` and official tipo-renta context to that same entry point. The public contract now states this ownership explicitly, preventing the future Notice projection from introducing a second matcher.

Focused Ruff passed. Focused pytest passed with 11 tests.

Independent review passed with no findings and reconfirmed by Vaultspec RAG plus exact-symbol search that the codebase owns one public resolver and one internal matcher.

## Notes

The actual M210 result/tipo inputs and typed Notice emission remain assigned to `W03.P11.S27`; this Step deliberately does not pre-empt that application wiring or create a resolver-shaped wrapper. A later reviewer rerun reached 11 passes and 11 unrelated failures because concurrent Modelo 303 and Modelo 322 registry edits failed authority-grade validation before resolver assertions; the isolated focused run above completed before those shared-tree edits and passed fully.
