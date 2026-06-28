---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'P06.S04'
related:
  - "[[2026-05-13-cli-workflow-redesign-config-repair-shape-plan]]"
---

# `cli-workflow-redesign` `P06.S04`

Audited `src/aeat/entrypoints/cli/_app_live.py` for stale `doctor`
references.

- Inspected (no modification needed): `src/aeat/entrypoints/cli/_app_live.py`

## Description

The live-app CLI module exposes `aeat app live filed` subcommands
(`list`, `capture`, `capture-sources`). A full-file grep for
`doctor` returned zero hits; every translation key the module
resolves lives under `cli.app.live.*` and none references the
renamed diagnostics namespace. No edit was required.
