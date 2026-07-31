---
tags: ["#exec", "#registry-authority-flow"]
date: '2026-05-20'
modified: '2026-07-17'
body_hash: 'sha256:f052fa8f538d696a3a73c49dda87b36c32a88bbdb30ee0974cd3a5c391c78cca'
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
