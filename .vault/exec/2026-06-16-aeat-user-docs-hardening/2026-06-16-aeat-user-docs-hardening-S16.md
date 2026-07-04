---
tags:
  - '#exec'
  - '#aeat-user-docs-hardening'
date: '2026-07-04'
modified: '2026-07-04'
step_id: 'S16'
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
     The S16 and 2026-06-16-aeat-user-docs-hardening-plan placeholders are machine-filled by
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
     The Harden justificante-receipts.md and ## Scope

- `docs/how-to/justificante-receipts.md` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Harden justificante-receipts.md

## Scope

- `docs/how-to/justificante-receipts.md`

## Description

- Verify-close: read `justificante-receipts.md` against its 2026-06-18-audit findings and the systemic patterns and confirm resolution at HEAD.
- Confirm S-AUTH: `justificante pull` is documented as live-only, needing configured authentication; when auth is not set up the pull refuses before contacting AEAT (the Cl@ve-identity refusal), directing the reader to authenticate.
- Confirm S-QUIET: the on-page profile-create hint includes `--quiet` (the non-interactive form), so a reader following the suggestion does not hit the interactive-wizard wall.
- Confirm S-PASS (passphrase prerequisite) and the required scope args (`--modelo`, `--year`, `--period`).

## Outcome

- Page verified compliant at HEAD; the S-AUTH, S-QUIET, S-PASS patterns are addressed. Delta: none required.

## Notes

- The receipt is pulled and stored as encrypted evidence in the profile (bytes-not-links). CLI conformance gate green.
