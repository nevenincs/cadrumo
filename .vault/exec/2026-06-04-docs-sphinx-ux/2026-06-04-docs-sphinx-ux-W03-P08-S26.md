---
tags:
  - '#exec'
  - '#docs-sphinx-ux'
date: '2026-07-15'
modified: '2026-07-15'
step_id: 'S26'
related:
  - "[[2026-06-04-docs-sphinx-ux-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace docs-sphinx-ux with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S26 and 2026-06-04-docs-sphinx-ux-plan placeholders are machine-filled by
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
     The record approved follow-up UX issues and ## Scope

- `.vault/exec/2026-06-04-docs-sphinx-ux` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# record approved follow-up UX issues

## Scope

- `.vault/exec/2026-06-04-docs-sphinx-ux`

## Description

- Collect every follow-up UX issue surfaced by the operator's approved
  review of the consolidated packet (brand, navigation, rendered
  experience) and record its disposition.

## Outcome

- The operator's single change request from the review — the generated CLI
  reference read as an unstructured command dump and should be separated by
  major verb group, each group opening with the real verb help output — was
  implemented inside this plan under the reference feedback-incorporation
  Step (generator restructure in `dev/docs/cli_reference.py`, per-group
  pages, canonical group ordering, captured help blocks; all reference and
  build gates green).
- No residual UX follow-up issues remain from the approved review: brand,
  route navigation, and the rendered desktop and mobile experience were
  approved without changes, and the two defects found during the rendered
  inspection (header-nav API retarget, IRPF lifecycle profile-create flag)
  were fixed before closure.
- With this record the plan's Step set is complete.

## Notes

- One non-UX housekeeping observation from the same session is tracked
  outside this plan: the example environment file still lists retired
  former-product variable names that the settings layer now deliberately
  ignores; that is a rename-residue cleanup, not a documentation UX issue.
