---
tags: ["#exec", "#registry-authority-flow"]
date: '2026-05-20'
modified: '2026-05-20'
step_id: 'S07'
related:
  - '[[2026-05-20-registry-authority-flow-plan]]'
---

# `registry-authority-flow` `W02.P03.S07`

Proved authority cache invalidation for changed fragmented TOML.

- Modified: `test_authority.py`
- Created: this execution record

## Description

Added a temp fragmented registry test that loads an authority, edits a revision fragment, reloads, and asserts a new authority sees the changed label.

## Tests

`uv run pytest src/aeat/domain/calculations/registry/test_authority.py -q` passed.
