---
tags:
  - '#exec'
  - '#binding-adr-corpus-reconciliation'
date: '2026-07-05'
modified: '2026-07-05'
step_id: 'S06'
related:
  - "[[2026-06-26-binding-adr-corpus-reconciliation-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace binding-adr-corpus-reconciliation with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S06 and 2026-06-26-binding-adr-corpus-reconciliation-plan placeholders are machine-filled by
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
     The REWORK: align the m390-annual-autoconsumo fold-in to the one carry mechanism (phase 2.3) and ## Scope

- `re-point from the apex`
- `.vault/adr/2026-06-02-m390-annual-autoconsumo-promotor-source-adr.md` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# REWORK: align the m390-annual-autoconsumo fold-in to the one carry mechanism (phase 2.3)

## Scope

- `re-point from the apex`
- `.vault/adr/2026-06-02-m390-annual-autoconsumo-promotor-source-adr.md`

## Description

- Reconstruct the execution record for the already-checked S06 row.
- Confirm commit `e511d8fed3` aligned `2026-06-02-m390-annual-autoconsumo-promotor-source-adr.md`.
- Verify the status block assigns unified carry direction to phase 2.3 and the wallet anchor.

## Outcome

- S06 is backed by landed evidence. The M390 annual fold-in arithmetic stands, and
  the ADR now states that future phase 2.3 unifies it with the one compensacion
  carry mechanism anchored by the live IVA wallet ADR.
- No source code or plan checkbox was changed in this reconciliation pass.

## Notes

- Reconstructed on 2026-07-05 because the step was checked without an exec record.
- Evidence command: `git show --stat --oneline e511d8fed3`.
