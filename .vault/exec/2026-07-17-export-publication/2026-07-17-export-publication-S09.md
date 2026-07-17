---
tags:
  - '#exec'
  - '#export-publication'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S09'
related:
  - "[[2026-07-17-export-publication-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace export-publication with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S09 and 2026-07-17-export-publication-plan placeholders are machine-filled by
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
     The Regenerate the operator reference pages for portable export and subject access from the frozen live surface and ## Scope

- `docs/reference/import-export-and-evidence.md` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Regenerate the operator reference pages for portable export and subject access from the frozen live surface

## Scope

- `docs/reference/import-export-and-evidence.md`

## Description

- Add portable-profile-export and subject-access-request rows to the export reference table in `docs/reference/import-export-and-evidence.md`, each naming what it produces and what it does not prove.
- Add a paragraph, grounded in the live command surface, describing the two purposes as one export service and one bundle schema, the derived data categories, the atomic staged-then-replaced publication, and the equal cleartext handoff risk both purposes carry.

## Outcome

The reference now covers the portable profile export and the subject-access request faithfully to the frozen live CLI surface. The documented-command inline-span gate passes and the nitpicky docs build passes.

## Notes

Command references are cited by bare command path (no option/arg tokens inline) to satisfy the user-doc inline-aeat-span baseline; options are described in prose. The reference doc is hand-authored under the documentation workflow, not a generator-managed file, so the change is an authored edit rather than a regenerated managed zone.
