---
tags:
  - '#exec'
  - '#binding-adr-corpus-reconciliation'
date: '2026-07-05'
modified: '2026-07-05'
step_id: 'S11'
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
     The S11 and 2026-06-26-binding-adr-corpus-reconciliation-plan placeholders are machine-filled by
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
     The DEMOTE the apex central ADR: set status to rejected with a note (apex declined by operator and ## Scope

- `C1-C6 analysis preserved in the research doc + this plan's verdict table`
- `canonical direction = phase + foundational ADRs)`
- `do NOT convert to research`
- `.vault/adr/2026-06-26-bindings-architecture-unification-adr.md` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# DEMOTE the apex central ADR: set status to rejected with a note (apex declined by operator

## Scope

- `C1-C6 analysis preserved in the research doc + this plan's verdict table`
- `canonical direction = phase + foundational ADRs)`
- `do NOT convert to research`
- `.vault/adr/2026-06-26-bindings-architecture-unification-adr.md`

## Description

- Reconstruct the execution record for the already-checked S11 row.
- Confirm commit `3edc8eba23` demoted `2026-06-26-bindings-architecture-unification-adr.md` to rejected.
- Verify the demotion note preserves C1-C6 analysis as input while denying apex authority.

## Outcome

- S11 is backed by landed evidence. The central bindings architecture apex ADR is
  rejected, the operator no-apex directive is recorded, and the canonical
  direction is the phase and foundational ADR set.
- No source code or plan checkbox was changed in this reconciliation pass.

## Notes

- Reconstructed on 2026-07-05 because the step was checked without an exec record.
- Evidence command: `git show --stat --oneline 3edc8eba23`.
