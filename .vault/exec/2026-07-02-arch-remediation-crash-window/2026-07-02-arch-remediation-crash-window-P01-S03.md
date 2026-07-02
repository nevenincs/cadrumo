---
tags:
  - '#exec'
  - '#arch-remediation-crash-window'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S03'
related:
  - "[[2026-07-02-arch-remediation-crash-window-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace arch-remediation-crash-window with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S03 and 2026-07-02-arch-remediation-crash-window-plan placeholders are machine-filled by
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
     The Confirm the hard-delete ordering at HEAD and resolve the partial-directory-detection-in-repair-integrity cell, updating the reference body with the finding and ## Scope

- `.vault/reference/2026-07-02-arch-remediation-crash-window-reference.md` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Confirm the hard-delete ordering at HEAD and resolve the partial-directory-detection-in-repair-integrity cell, updating the reference body with the finding

## Scope

- `.vault/reference/2026-07-02-arch-remediation-crash-window-reference.md`

## Description

Read the hard-delete ordering at HEAD; recorded soft tombstone then trash-rename whole-directory removal, and the idempotent re-run plus readiness refusal plus scan-issue detection. Resolved the partial-directory-detection-in-repair-integrity cell in the reference body.

## Outcome

Confirmed guarantee: idempotent re-removal, non-ready health refusal, and torn-manifest partial-directory detection.

## Notes

A partial directory whose manifest is absent is excluded from the live inventory as reclaimable garbage, consistent with create-rollback staging semantics.
