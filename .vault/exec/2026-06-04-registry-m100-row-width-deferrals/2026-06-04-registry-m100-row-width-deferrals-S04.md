---
tags:
  - '#exec'
  - '#registry-m100-row-width-deferrals'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S04'
related:
  - '[[2026-06-04-registry-m100-row-width-deferrals-plan]]'
---

# S04 Row-Width Baseline Tightening

Scope: tighten the TOML row-width baseline after closing the M100 deferred rows.

## Description

- Lowered `_MAX_BASELINE_TOML_LINE_CHARS` from 555 to 530 in `test_registry_reviewability.py`.
- Chose 530 because the post-S03 widest registry TOML row is 528 characters and the assertion uses a strict `<` comparison.
- Left the hard cap unchanged at 600 characters.

## Outcome

- `uv run --no-sync ruff check src/aeat/domain/calculations/registry/test_registry_reviewability.py` passed.
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_registry_reviewability.py -q` passed: 3 passed.
- Post-S04 widest row is `100/revisions/2025/casillas/0615-0549.toml:7` at 528 characters.

## Notes

- Further tightening below 530 should wait for a separate M100 2025 legal-ref row pass.
