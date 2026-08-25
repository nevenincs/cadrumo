---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:b6764f1c3c4edace211a4593a3ee8f0c190556d41ef4651fb620b02ac2830463'
step_id: 'S79'
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
     The S79 and 2026-08-11-tui-architecture-plan placeholders are machine-filled by
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
     The Remove status-screen imports and project backend status through the CLI surface only and ## Scope

- `src/cadrumo/entrypoints/cli/_config/_status_frontend.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Remove status-screen imports and project backend status through the CLI surface only

## Scope

- `src/cadrumo/entrypoints/cli/_config/_status_frontend.py`

## Description

- Move status assembly, notices, deadlines, identity, workflow-state, and masking behavior to the public `application.user_profile.status_projection` defining module.
- Migrate the TUI status view and CLI status command to direct defining-module imports.
- Delete the CLI-owned status-screen constructor and its duplicated tests without retaining a facade or shim.

## Outcome

Status projection has one application-owned defining home. The CLI status path is CLI-only and imports no TUI implementation; the TUI imports the same canonical projection directly. Exact review found no scoped re-export, duplicate authority, or compatibility surface.

Independent review approved S79. The combined application/status/TUI gate passed all scoped behavior cases.

## Notes

Broad import-hygiene execution remains affected by concurrent malformed debt and migration-digest work outside S79; scoped behavior and exact ownership evidence are green.
