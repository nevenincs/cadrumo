---
tags:
  - '#exec'
  - '#arch-remediation-crash-window'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S01'
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
     The S01 and 2026-07-02-arch-remediation-crash-window-plan placeholders are machine-filled by
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
     The Confirm the create-profile write ordering at HEAD and resolve the rollback-covers-every-window-including-K-without-S cell, updating the reference body with the finding and ## Scope

- `.vault/reference/2026-07-02-arch-remediation-crash-window-reference.md` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Confirm the create-profile write ordering at HEAD and resolve the rollback-covers-every-window-including-K-without-S cell, updating the reference body with the finding

## Scope

- `.vault/reference/2026-07-02-arch-remediation-crash-window-reference.md`

## Description

Read the create-profile write ordering at HEAD across the create storage span and the profile repository; recorded that the wrapped DEK (K) is minted by the span before the encrypted record (S), and that create sequences dirs then manifest then pointer then record. Resolved the rollback-covers-every-window-including-K-without-S cell in the reference body.

## Outcome

Confirmed guarantee: the two-layer rollback (span DEK/keystore cleanup plus repository dir/manifest/pointer rollback) covers every window including K-without-S.

## Notes

The matrix ordering `dirs, then K, then S, then M` was wrong; the HEAD order is K (span), dirs, M, pointer, S. Recorded in the reference.
