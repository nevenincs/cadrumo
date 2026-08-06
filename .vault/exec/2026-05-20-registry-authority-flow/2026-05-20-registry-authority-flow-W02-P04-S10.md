---
tags: ["#exec", "#registry-authority-flow"]
date: '2026-05-20'
modified: '2026-07-17'
body_hash: 'sha256:f8514187b2d52bac5273920c16e1c9d4d07435a55963308a817b2b9c1061d166'
step_id: 'S10'
related:
  - '[[2026-05-20-registry-authority-flow-plan]]'
---

# `registry-authority-flow` `W02.P04.S10`

Covered duplicate export field fragments.

- Modified: `test_loader_directory_mode.py`
- Created: this execution record

## Description

Added a directory-mode temp registry test with two same-record fragments appending the same field id and asserting `RegistryLoadError`.

## Tests

`uv run pytest src/aeat/domain/calculations/registry/test_loader_directory_mode.py -q` passed.
