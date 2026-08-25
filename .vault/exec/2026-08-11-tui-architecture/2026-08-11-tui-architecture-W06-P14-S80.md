---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:04c8a4b7953706fc9d3048bab6c5b75435ac2909a4a247926ece0fa94e5760ee'
step_id: 'S80'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace tui-architecture with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S80 and 2026-08-11-tui-architecture-plan placeholders are machine-filled by
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
     The Replace profile-bundle TUI imports with application flow and operation facades and ## Scope

- `src/cadrumo/entrypoints/cli/_config/_profile_bundle_flow.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Replace profile-bundle TUI imports with application flow and operation facades

## Scope

- `src/cadrumo/entrypoints/cli/_config/_profile_bundle_flow.py`

## Description

- Delete the former profile-bundle flow and its export/import command registrations rather than migrating a dead frontend.
- Retain the canonical profile archive-export and restore commands as the sole transfer surfaces.
- Add a live command-graph gate proving both retired profile-root leaves neither resolve nor register.
- Prove the surviving archive-export and restore leaves resolve to their authored schema identities.

## Outcome

S80 is closed as retired and superseded, not as a migrated implementation. The former profile-bundle TUI consumer and its command leaves are absent, while the current archive-export and restore commands remain authoritative.

The focused command-graph suite passes nine cases. Independent review approved the exact deletion and negative-registration evidence with no shim, re-export, or compatibility path.

## Notes

The obsolete implementation was deleted in `c4732174186`. The closure gate intentionally fails if either retired leaf re-enters the graph or registration metadata.
