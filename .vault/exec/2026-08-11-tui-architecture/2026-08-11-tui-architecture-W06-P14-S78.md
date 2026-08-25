---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:fcc1d64e56a614298a824db3cc26b63f122d6caa2f67f58abcd71f6d36a95782'
step_id: 'S78'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

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
