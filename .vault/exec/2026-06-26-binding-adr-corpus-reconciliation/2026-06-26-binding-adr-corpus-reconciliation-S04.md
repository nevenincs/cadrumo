---
tags:
  - '#exec'
  - '#binding-adr-corpus-reconciliation'
date: '2026-07-05'
modified: '2026-07-05'
step_id: 'S04'
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
     The S04 and 2026-06-26-binding-adr-corpus-reconciliation-plan placeholders are machine-filled by
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
     The REWORK: keep the bindings CLI surface and ## Scope

- `record the operator_surface.SourceKind duplicate as superseded by phase 2.1 and CLI vocabulary aligned in phase 2.4`
- `.vault/adr/2026-05-12-cli-workflow-redesign-app-modelo-bindings-shape-adr.md` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# REWORK: keep the bindings CLI surface

## Scope

- `record the operator_surface.SourceKind duplicate as superseded by phase 2.1 and CLI vocabulary aligned in phase 2.4`
- `.vault/adr/2026-05-12-cli-workflow-redesign-app-modelo-bindings-shape-adr.md`

## Description

- Reconstruct the execution record for the already-checked S04 row.
- Confirm commit `648f290cb6` reworked `2026-05-12-cli-workflow-redesign-app-modelo-bindings-shape-adr.md`.
- Verify the status block keeps the bindings CLI surface while superseding the duplicate `operator_surface.SourceKind`.

## Outcome

- S04 is backed by landed evidence. The bindings list and preview surface remains
  accepted, while the duplicate `operator_surface.SourceKind` is superseded by
  the phase 2.1 source-kind taxonomy and CLI vocabulary alignment is assigned to
  future phase 2.4.
- No source code or plan checkbox was changed in this reconciliation pass.

## Notes

- Reconstructed on 2026-07-05 because the step was checked without an exec record.
- Evidence command: `git show --stat --oneline 648f290cb6`.
