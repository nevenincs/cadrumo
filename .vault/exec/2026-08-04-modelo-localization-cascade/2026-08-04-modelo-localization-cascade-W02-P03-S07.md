---
tags:
  - '#exec'
  - '#modelo-localization-cascade'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:8af180e0a14eca2ba23b4a9231ecef02bd2471fbba8f078fd23e1abc32037f34'
step_id: 'S07'
related:
  - "[[2026-08-04-modelo-localization-cascade-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace modelo-localization-cascade with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S07 and 2026-08-04-modelo-localization-cascade-plan placeholders are machine-filled by
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
     The Emit explicit applicability variants, exact occurrence entries, and tombstones that preserve prior fallback behavior and ## Scope

- `dev/registry/migration` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Emit explicit applicability variants, exact occurrence entries, and tombstones that preserve prior fallback behavior

## Scope

- `dev/registry/migration`

## Description

- Reconcile exact-occurrence, continuidad, applicability, and retirement behavior with the live identity chain.
- Verify that source values remain in the shared Spanish catalogue and are not duplicated in revision schemas.
- Preserve any future semantic retirement or continuity conflict as an explicit review boundary.

## Outcome

Resolved by `ced27b5a59` and the live resolver contract. Exact occurrence keys
fall back through grounded continuidad keys and then the mandatory Spanish
source; no temporary variant/tombstone emitter is retained.

## Notes

No post-cutover staging catalogue was emitted. The historical migration row is
closed because the production contract is already the root-only outcome; a
future ungrounded retirement remains manual review, not duplicated locale data.
