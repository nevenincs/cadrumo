---
tags:
  - '#exec'
  - '#aeat-user-docs-hardening'
date: '2026-07-04'
modified: '2026-07-04'
step_id: 'S25'
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
     The S25 and 2026-06-16-aeat-user-docs-hardening-plan placeholders are machine-filled by
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
     The Harden read-live-aeat-data.md and ## Scope

- `docs/how-to/read-live-aeat-data.md` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Harden read-live-aeat-data.md

## Scope

- `docs/how-to/read-live-aeat-data.md`

## Description

- Verify-close: read `read-live-aeat-data.md` against its 2026-06-18-audit findings and confirm resolution at HEAD.
- Confirm finding M21 (documented `pull` commands miss required args): the page now shows the required scope per verb - `justificante pull --modelo --year --period` (all three required), `filed pull --modelo --year` (`--year` required, `--period` or `--from-year`/`--to-year` to narrow), `notifications pull` (no scope).
- Confirm the systemic S-AUTH pattern: the page explains that the "Cl@ve identity" refusal actually means authentication is not configured (`auth_configured=False`), directing the reader to configure a provider rather than chase a Cl@ve mismatch.
- Confirm the never-write boundary and the `AEAT_LIVE_TESTS_ENABLED`-is-a-developer-setting clarification are stated.

## Outcome

- Page verified compliant at HEAD; finding M21 and the S-AUTH pattern resolved (2026-06-19 documentation batch). Delta: none required.

## Notes

- Read-only boundary is prominent ("never writes, files, or submits"); pull-vs-apply separation documented. CLI conformance gate green.
