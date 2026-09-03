---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:e6f29d62b08830af0957a50324ca5aaec89d23b819e29aea03175b0422db733b'
step_id: 'S402'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---


# Expose one operation composition result containing services and the exact public contract set from the same registry so workbench actions and modals cannot drift

## Scope

- `src/cadrumo/application/operations/composition.py`
- `src/cadrumo/entrypoints/tui/launcher.py`
- `and focused composition tests`

## Changes

