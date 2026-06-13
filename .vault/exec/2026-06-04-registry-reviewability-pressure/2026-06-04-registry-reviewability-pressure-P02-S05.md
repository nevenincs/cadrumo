---
tags:
  - '#exec'
  - '#registry-reviewability-pressure'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S05'
related:
  - '[[2026-06-04-registry-reviewability-pressure-plan]]'
---

# `registry-reviewability-pressure` `P02.S05` gate

Scope: tighten reviewability regression gates after corpus pressure headroom is
improved.

## Description

- Tightened the committed TOML baseline line-count gate from 1,250 lines to
  1,100 lines.
- Left the hard cap at 1,500 lines.
- Left the row-width baseline at 575 characters because M100 row formatting is
  a separate unresolved pressure target.

## Outcome

S05 completed. The reviewability baseline now prevents M123-style growth from
returning while keeping the current post-split corpus green.

## Notes

Verification:

- `uv run --no-sync ruff check src/aeat/domain/calculations/registry/test_registry_reviewability.py` passed.
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_registry_reviewability.py -q` passed: 3 tests.
- Post-split largest TOML: `303/revisions/2023-y-siguientes/revision.toml`, 1,033 lines.
- Post-split widest row: `100/revisions/2025/casillas/0618-0552.toml`, 572 characters.
