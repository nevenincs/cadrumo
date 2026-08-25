---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:8f2cc337a270d52b2e406126059a1ccd9e8db03ac45e7b4a658ce906e69c53e2'
step_id: 'S78'
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
     The S78 and 2026-08-11-tui-architecture-plan placeholders are machine-filled by
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
     The Remove login TUI construction and consume the application authentication operation contract and ## Scope

- `src/cadrumo/entrypoints/cli/_config/_login_frontend.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Remove login TUI construction and consume the application authentication operation contract

## Scope

- `src/cadrumo/entrypoints/cli/_config/_login_frontend.py`

## Description

- Move chooser, preselection, login-attempt DTOs, and expected-refusal classification to the public `application.user_profile.login_interaction` defining module.
- Migrate CLI and TUI consumers to direct defining-module imports.
- Delete the CLI-owned login TUI constructor and its tests without a facade, shim, or re-export.
- Pin the exact three-member expected authentication refusal family without mocks or monkeypatching.

## Outcome

Login interaction behavior now has one frontend-neutral application owner. CLI code no longer imports or constructs a TUI login screen, while the canonical TUI consumes the same login contract directly. Unexpected application errors remain propagating defects rather than being laundered into operator refusal data.

Independent review approved S78. Scoped Ruff passed and the real integration module passed five tests.

## Notes

The shared migration-manifest digest is moving under concurrent TUI work and was not rewritten as part of this semantic owner move.
