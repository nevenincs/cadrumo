---
tags:
  - '#exec'
  - '#aeat-user-docs-hardening'
date: '2026-07-04'
modified: '2026-07-04'
step_id: 'S10'
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
     The S10 and 2026-06-16-aeat-user-docs-hardening-plan placeholders are machine-filled by
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
     The Harden filing-calendar.md and ## Scope

- `docs/how-to/filing-calendar.md` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Harden filing-calendar.md

## Scope

- `docs/how-to/filing-calendar.md`

## Description

- Verify-close: read `filing-calendar.md` against its 2026-06-18-audit finding M12 and confirm resolution at HEAD.
- Confirm M12 (`overview calendar` refuses on an undocumented `censo.enrolment_unverified` gate while agenda/backlog/explain succeed; the "Before you start" undersold setup): the page now documents `--allow-incomplete` where the command accepts it (agenda/backlog and calendar) so a fresh profile runs, and names the `censo.enrolment_unverified` unresolved-check case explicitly.

## Outcome

- Page verified compliant at HEAD; finding M12 resolved. Delta: none required. CLI conformance gate green.

## Notes

- The calendar-vs-agenda gate difference is documented rather than surprising the reader.
