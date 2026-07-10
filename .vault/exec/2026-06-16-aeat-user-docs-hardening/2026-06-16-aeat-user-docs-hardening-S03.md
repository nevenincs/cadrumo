---
tags:
  - '#exec'
  - '#aeat-user-docs-hardening'
date: '2026-07-04'
modified: '2026-07-04'
step_id: 'S03'
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
     The S03 and 2026-06-16-aeat-user-docs-hardening-plan placeholders are machine-filled by
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
     The Harden check-aeat-notifications.md and ## Scope

- `docs/how-to/check-aeat-notifications.md` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Harden check-aeat-notifications.md

## Scope

- `docs/how-to/check-aeat-notifications.md`

## Description

- Verify-close: read `check-aeat-notifications.md` against its 2026-06-18-audit findings and confirm resolution at HEAD.
- Confirm finding B3 (`portals list` un-runnable): the page now shows a runnable `aeat app live portals list`, narrowed by `--modelo` OR by `--category` (with the accepted category enum), rather than the invalid `--category sede_modelo` + mutually-exclusive `--modelo` combination.
- Confirm finding M23 (`filed list` mislabelled as non-downloading): the page documents `filed list --modelo --from-year --to-year` as a live AEAT read, with the local views (`list`/`latest`/`view`/`history`) working offline after a profile exists.
- Confirm the live pull verbs show their required args.

## Outcome

- Page verified compliant at HEAD; findings B3 and M23 resolved (2026-06-19 documentation batch). Delta: none required.

## Notes

- All `aeat app live ...` verbs cited resolve against the live surface (conformance gate). CLI conformance gate green.
