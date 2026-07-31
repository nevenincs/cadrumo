---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-07-31'
body_hash: 'sha256:a44ed9b55f7b3e7912cb951c1efe640ea7951de1684231c65b9e703c60623ab7'
related:
  - "[[2026-05-13-cli-workflow-redesign-config-repair-shape-plan]]"
---

# `cli-workflow-redesign` `P06.S05`

Audited `src/aeat/entrypoints/cli/_common.py` for stale `doctor`
references in docstrings, prompt strings, and emitter hints.

- Inspected (no modification needed): `src/aeat/entrypoints/cli/_common.py`

## Description

`_common.py` carries the CLI's `_emit`, `_bad`, `_exit`, period
normaliser, repository helpers, and the renta filing input
aggregator. A full-file grep for `doctor` returned zero hits — no
docstring, prompt string, or hint mentions the old namespace. No
edit was required.
