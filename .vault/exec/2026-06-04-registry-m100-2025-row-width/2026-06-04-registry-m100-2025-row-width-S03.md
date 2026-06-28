---
tags:
  - '#exec'
  - '#registry-m100-2025-row-width'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S03'
related:
  - '[[2026-06-04-registry-m100-2025-row-width-plan]]'
---

# S03 Row-Width Baseline Tightening

Scope: tighten the TOML row-width baseline after formatting M100 2025 rows above 520 characters.

## Description

- Lowered `_MAX_BASELINE_TOML_LINE_CHARS` from 530 to 520 in `test_registry_reviewability.py`.
- Chose 520 because the post-S02 widest registry TOML row is 517 characters.
- Left the hard cap unchanged at 600 characters.

## Outcome

- `uv run --no-sync ruff check src/aeat/domain/calculations/registry/test_registry_reviewability.py` passed.
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_registry_reviewability.py -q` passed: 3 passed.
- Post-S03 widest row is `200/revisions/2024-y-siguientes/casillas/0029-base-imponible-negativa-o-cero.toml:8` at 517 characters.

## Notes

- Further tightening below 520 should be handled by a separate non-M100 row-width pass.
