---
tags: ["#exec", "#registry-authority-flow"]
date: '2026-05-20'
modified: '2026-05-20'
step_id: 'S14'
related:
  - '[[2026-05-20-registry-authority-flow-plan]]'
---

# `registry-authority-flow` `W03.P06.S14`

Migrated Sede declaration registry loading to authority snapshots.

- Modified: `_declarations.py`
- Created: this execution record

## Description

Replaced raw loader and local snapshot construction in the Sede declaration parser with a cached authority accessor and authority-owned snapshot selection.

## Tests

`uv run pytest src/aeat/adapters/outbound/aeat/sede/test_declarations.py -q` passed.
