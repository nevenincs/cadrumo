---
tags:
  - '#exec'
  - '#aeat-user-docs-hardening'
date: '2026-07-04'
modified: '2026-07-04'
step_id: 'S27'
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
     The S27 and 2026-06-16-aeat-user-docs-hardening-plan placeholders are machine-filled by
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
     The Harden review-calculation-values.md and ## Scope

- `docs/how-to/review-calculation-values.md` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Harden review-calculation-values.md

## Scope

- `docs/how-to/review-calculation-values.md`

## Description

- Verify-close: read `review-calculation-values.md` against its 2026-06-18-audit findings and confirm resolution at HEAD.
- Confirm finding M9 (ordering inversion + headline example fails): the page now sequences the work-unit create in "Before you start" first, states that the review commands refuse on a fresh unit and point to calculate first, and its `--casilla` example uses the manual box `06` (Retenciones), not the bound box `02` (Gastos), which `--casilla` refuses.
- Confirm finding m5 (`bindings list --missing` / readiness restatement): the page documents the `source` and `readiness` labels accurately and how to supply each source kind.
- Confirm S-PASS (passphrase) and S-PREREQ (active-profile + work-unit prerequisites) are addressed.

## Outcome

- Page verified compliant at HEAD; findings M9, m5, S-PASS, S-PREREQ resolved (2026-06-19 documentation batch). Delta: none required.

## Notes

- Documents the manual-vs-bound casilla distinction and the first-period prior-binding `=0` convention correctly. CLI conformance gate green.
