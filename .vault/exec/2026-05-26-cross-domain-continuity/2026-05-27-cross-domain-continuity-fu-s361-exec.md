---
step_id: FU-S361
tags:
  - "#exec"
  - "#cross-domain-continuity"
date: 2026-05-27
modified: '2026-05-27'
related:
  - "[[2026-05-27-cross-domain-continuity-w09-p41-s361-review-exec]]"
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# FU-S361: add aeat-renta-2024-manual-parte1 to 0172 formula source_refs

## Outcome

Closed REGISTRY-001 LOW from the S361 review. Formula `renta-2024-total-pagos-a-cuenta` now cites `aeat-renta-2024-manual-parte1` consistently with all other settlement formulas in the chain.

## Commit

Pending — staged, commit follows.

## Changes

- `src/aeat/_data/registry/aeat/modelos/100/revisions/2024/formulas/0172-renta-2024-total-pagos-a-cuenta.toml`: Added `aeat-renta-2024-manual-parte1` to `source_refs` list. Pattern matches the five peer formulas (0169–0174) that already cite this source.

## Gates

- 6/6 settlement chain tests pass
- No Python changed; ruff/pyright not applicable
- Registry loaded cleanly by the settlement chain test suite
