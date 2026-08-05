---
tags:
  - '#exec'
  - '#modelo-localization-cascade'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:b695228034f6c9150914ee14bd9985d56a9253ab277a05d25a8292423d2b644e'
step_id: 'S08'
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
     The S08 and 2026-08-04-modelo-localization-cascade-plan placeholders are machine-filled by
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
     The Implement a dry-run command with an explicit temporary-output contract and no live-registry destination and ## Scope

- `dev/registry/migration` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Implement a dry-run command with an explicit temporary-output contract and no live-registry destination

## Scope

- `dev/registry/migration`

## Description

- Verify that the disposable dry-run command is not part of the live production surface.
- Verify that no migration command can target the live registry after cutover.
- Retain the refusal boundary in the cutover and new-Modelo scaffold contracts.

## Outcome

Superseded by the landed cutover. `dev/registry/migration` is absent, so there
is no dry-run writer or live-registry destination to invoke; the production
surface exposes the shared locale CLI and runtime loader only.

## Notes

The temporary application was deleted deliberately. Restoring it would violate
the no-legacy-support boundary and would not add a production capability.
