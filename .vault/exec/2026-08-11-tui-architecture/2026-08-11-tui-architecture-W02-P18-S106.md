---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:2d8dbd6624816a29eabdf2da453e3ba2081e795b86aad36b4845d0241f0a51c3'
step_id: 'S106'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Refuse unenrolled TUI routes through a typed localized command-boundary error

## Scope

- `src/cadrumo/entrypoints/cli/_command_runtime.py`
- `src/cadrumo/entrypoints/cli/_errors.py`
- `src/cadrumo/core/errors/registry/_entrypoints.py`

## Description

Add a registered typed refusal and enforce it before command preflight or handler resolution.

## Outcome

Unimplemented TUI requests return `TUI_NOT_IMPLEMENTED` without profile, storage, or command side effects.

## Notes

No CLI-to-TUI import or silent line-mode fallback was introduced.
