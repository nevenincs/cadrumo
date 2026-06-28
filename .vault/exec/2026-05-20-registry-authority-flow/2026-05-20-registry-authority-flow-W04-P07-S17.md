---
tags: ["#exec", "#registry-authority-flow"]
date: '2026-05-20'
modified: '2026-05-20'
step_id: 'S17'
related:
  - '[[2026-05-20-registry-authority-flow-plan]]'
---

# `registry-authority-flow` `W04.P07.S17`

Added authority snapshot boundary assertions.

- Modified: `test_authority.py`
- Created: this execution record

## Description

Asserted that authority snapshots project the authority-owned modelo and selected revision, cache repeated filing-context requests, and mark the modelo as validated.

## Tests

`uv run pytest src/aeat/domain/calculations/registry/test_authority.py -q` passed.
