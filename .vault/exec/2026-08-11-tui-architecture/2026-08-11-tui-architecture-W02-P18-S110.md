---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:37ffea4625287b1dbdd5bc43e03977e9c3669e01d4a505c035f1bfb60b027790'
step_id: 'S110'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Enroll the complete existing eight-route TUI surface and remove the accidental leaf-local option

## Scope

- `src/cadrumo/entrypoints/cli/_config`
- `src/cadrumo/entrypoints/cli/_modelo_work_command_specs.py`
- `src/cadrumo/entrypoints/cli/_modelo_nonwork_command_specs.py`

## Description

- Mark all eight real full-screen command nodes `AVAILABLE`.
- Remove the profile leaf-local `--tui` option.
- Read the root request directly at profile frontend dispatch.

## Outcome

Completed. The closed command graph now matches the audited runtime surface.

## Notes

No new TUI consumer or presentation implementation was added.
