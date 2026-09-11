---
tags:
  - '#exec'
  - '#justfile-design'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:8220a3fac10a3320b07e5227bbcbce52dd37a4f797a09328a189dc61e80ed730'
step_id: 'S31'
related:
  - "[[2026-09-11-justfile-design-plan]]"
---

# Replace the generic locale pass-through with authority-consistent locale operations or demote it

## Scope

- `justfile`

## Changes

- `M` `justfile`
- `verify:` `just --dry-run locales-set es demo.key "Texto con spaces"` -> `pass`
