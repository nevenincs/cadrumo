---
tags:
  - '#exec'
  - '#modelo-localization-cascade'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:acf012401f6a81128bd711ade0540c3cd4155361b9f0d5f748dd9dfe24bb8b76'
step_id: 'S10'
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
     The S10 and 2026-08-04-modelo-localization-cascade-plan placeholders are machine-filled by
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
     The Reject live-registry paths and every non-certified production-write mode during migration-app execution and ## Scope

- `dev/registry/migration` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Reject live-registry paths and every non-certified production-write mode during migration-app execution

## Scope

- `dev/registry/migration`

## Description

- Verify that no migration-app production-write mode remains in the live tree.
- Verify that new Modelo scaffolding refuses revision-local locale storage.
- Close the historical refusal row against the root-only cutover boundary.

## Outcome

Resolved by absence and by the new-Modelo scaffold guard in
`dev/registry/newmodelo/tests/test_manager.py:52-53`. The deleted disposable
application cannot write the live registry, and new enrollment has no legacy
locale-directory creation path.

## Notes

No compatibility or deprecated write mode was retained.
