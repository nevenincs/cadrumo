---
tags:
  - '#exec'
  - '#arch-remediation-crash-window'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S07'
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
     The S07 and 2026-07-02-arch-remediation-crash-window-plan placeholders are machine-filled by
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
     The Confirm the master-key rotation ordering at HEAD and resolve the mixed-key window across envelope files, blob manifests, and the keystore, updating the reference body with the finding and ## Scope

- `.vault/reference/2026-07-02-arch-remediation-crash-window-reference.md` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Confirm the master-key rotation ordering at HEAD and resolve the mixed-key window across envelope files, blob manifests, and the keystore, updating the reference body with the finding

## Scope

- `.vault/reference/2026-07-02-arch-remediation-crash-window-reference.md`

## Description

Read the master-key rotation ordering at HEAD across the two rotation primitives and the keystore DEK; recorded per-store probe-skip idempotency and the absence of a single orchestrator. Resolved the mixed-key window across envelope files, blob manifests, and the keystore in the reference body.

## Outcome

Confirmed guarantee: per-store probe-skip idempotent recovery of the mixed-key window; the keystore DEK re-wrap is value-preserving and custody-owned, and secure_objects is intentionally not rotated.

## Notes

No application-layer orchestrator wires the two ciphertext rotation primitives together; the mixed-key recovery is a re-run of both.
