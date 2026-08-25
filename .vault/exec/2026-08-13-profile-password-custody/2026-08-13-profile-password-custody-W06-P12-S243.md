---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:b2d3c3af9e3626361966cb04a6b675b99967d997ba90e7600e184f6144b66b83'
step_id: 'S243'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace profile-password-custody with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S243 and 2026-08-13-profile-password-custody-plan placeholders are machine-filled by
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
     The Repair Spanish, Catalan, and Hungarian localized reference tokens and generated CLI toctree integration so all localized nitpicky builds resolve current targets and ## Scope

- `docs/locales/ and docs/reference/cli/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Repair Spanish, Catalan, and Hungarian localized reference tokens and generated CLI toctree integration so all localized nitpicky builds resolve current targets

## Scope

- `docs/locales/ and docs/reference/cli/`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

- Trace localized token and generated CLI-reference ownership through semantic discovery and exact source confirmation.
- Restore exact Markdown targets in the Spanish, Catalan, and Hungarian messages reported as inconsistent.
- Replace a stale translated filing paragraph with substantive current-language prose carrying no invented reference.
- Enrol every generated nested CLI group page in its owning family page's hidden toctree.
- Add a graph-derived test proving every generated nested group has one family-toctree entry.
- Run catalogue completeness and drift, PO parsing, generator gates, localized nitpicky builds, Ruff, and formal review.

## Outcome

Spanish, Catalan, and Hungarian builds preserve the exact source reference-token sets for the three failing messages. The CLI generator now places all seventeen nested group pages under their five family landing-page toctrees without hand-editing generated files. Fourteen localization and CLI-reference tests pass, every PO file parses, Ruff passes, isolated coherent-HEAD nitpicky builds pass for all three languages, and formal review approved with no findings.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->

The live shared-tree build is obstructed before documentation parsing by a concurrent Modelo 721 revision split. The localized builds therefore ran against an isolated HEAD snapshot with the S243 files overlaid and only the peer-blocked casilla generator replaced; all passed.

The fresh catalogue-drift gate ran and remains red on fourteen pages whose source/catalogue drift predates and lies outside the three S243 token messages. Catalogue completeness and all S243-owned msgids are green. No generated CLI reference page was edited or committed.
