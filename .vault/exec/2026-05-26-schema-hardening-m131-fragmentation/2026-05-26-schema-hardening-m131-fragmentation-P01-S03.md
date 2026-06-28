---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-26'
modified: '2026-05-26'
step_id: 'S03'
related:
  - '[[2026-05-26-schema-hardening-m131-fragmentation-plan]]'
---

# `schema-hardening-m131-fragmentation` `P01.S03`

Verified the M131 fragment split against loader discovery, committed-registry
integrity, referential checks, and TOML reviewability baselines.

- Modified: `.vault/plan/2026-05-26-schema-hardening-m131-fragmentation-plan.md`

## Description

Post-split discovery reports Modelo 131 as a directory-mode modelo with four
fragment-directory revisions: `2019-2023`, `2024`, `2025`, and `2026`.
Fragment counts are 15, 16, 16, and 17 respectively.

The largest M131 fragment is now 624 lines. The largest committed TOML files
seen in the registry after the split are M200 export fragments at 1,500 and
1,496 lines and the M130 single-file modelo at 1,496 lines, all below the
current 1,750-line TOML fragment gate.

## Tests

Validation completed:

- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_modelo_131_registry.py src/aeat/domain/calculations/registry/test_loader_directory_mode.py src/aeat/domain/calculations/registry/test_committed_registry.py src/aeat/domain/calculations/registry/test_referential_integrity.py -q`
- `117 passed in 132.74s`
