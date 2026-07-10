---
tags:
  - '#exec'
  - '#aeat-user-docs-hardening'
date: '2026-07-04'
modified: '2026-07-04'
step_id: 'S02'
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
     The S02 and 2026-06-16-aeat-user-docs-hardening-plan placeholders are machine-filled by
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
     The Harden censo-update.md and ## Scope

- `docs/how-to/censo-update.md` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Harden censo-update.md

## Scope

- `docs/how-to/censo-update.md`

## Description

- Verify-close: read `censo-update.md` against its 2026-06-18-audit findings (the systemic S-AUTH / S-PASS / S-PREREQ patterns that touch every live-read page) and confirm resolution at HEAD.
- Confirm S-AUTH: the page requires configured read-only AEAT authentication and links the authenticate guide; the pull-vs-apply separation is explicit (pull saves a snapshot, apply writes reviewed facts locally, nothing is submitted to AEAT).
- Confirm S-PASS (master-key passphrase prerequisite) and the never-file-036 / never-submit boundary are stated.

## Outcome

- Page verified compliant at HEAD; the S-AUTH / S-PASS patterns are addressed. Delta: none required.

## Notes

- `aeat config profile censo pull` / compare / apply cited per the pull-and-file standard; local audit history documented. CLI conformance gate green.
