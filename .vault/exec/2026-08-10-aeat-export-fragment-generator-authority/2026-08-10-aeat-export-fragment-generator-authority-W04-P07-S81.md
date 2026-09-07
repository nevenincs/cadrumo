---
tags:
  - '#exec'
  - '#aeat-export-fragment-generator-authority'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:cf0ce8b787a994c54d8cd22aff8ea1d37b238a2901632d7c864ea18c10c3ce11'
step_id: 'S81'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---

# Author and hand-review the Modelo 390 2024 exact-source semantic map and exhaustive source-bound render profile, bijecting all 621 numbered-page fixed anchors plus the separately governed 13-anchor auxiliary header for 634 parsed anchors total by carrying the 2024 revision's 477 exact layout owners and 130 exact binding owners, explicitly classifying 14 reserved fillers, preserving the payloads of all 341 parser-stable anchors, reviewing all 200 changed and 80 added anchors including the two Lorca replacements and nine DANA additions, and proving the nine numbered-record composition renders without a source-defect pin

## Scope

- `dev/registry/mappings/modelo_390/2024/`
- `dev/registry/render_profiles/modelo_390/2024/`
- `dev/registry/tests/test_m390_2024_semantic_map.py`

## Changes

- `A` `dev/registry/mappings/modelo_390/2024/0001-records.toml`
- `A` `dev/registry/mappings/modelo_390/2024/0002-entries.toml`
- `A` `dev/registry/render_profiles/modelo_390/2024/0001-numeric-representation.toml`
- `A` `dev/registry/tests/test_m390_2024_semantic_map.py`
- `M` `.vault/plan/2026-08-10-aeat-export-fragment-generator-authority-plan.md`
- `A` `.vault/audit/2026-09-07-aeat-export-fragment-generator-authority-s81-semantic-map-review-audit.md`
- `M` `.vault/index/aeat-export-fragment-generator-authority.index.md`
- `verify:` `uv run --no-sync pytest -q dev/registry/tests/test_m390_2024_semantic_map.py` -> `pass (2 passed)`
- `verify:` `uv run --no-sync basedpyright dev/registry/tests/test_m390_2024_semantic_map.py` -> `pass (0 errors, 0 warnings, 0 notes)`
- `verify:` `uv run --no-sync ruff check dev/registry/tests/test_m390_2024_semantic_map.py` -> `pass`
- `verify:` `uv run --no-sync ruff format --check dev/registry/tests/test_m390_2024_semantic_map.py` -> `pass`
