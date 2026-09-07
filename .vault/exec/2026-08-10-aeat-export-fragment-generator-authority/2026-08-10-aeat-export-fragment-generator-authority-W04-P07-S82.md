---
tags:
  - '#exec'
  - '#aeat-export-fragment-generator-authority'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:785f97e8ddb16e0f357eb01ae42fd6cf041e9b5e54ef6c0332fcf699e9296cf6'
step_id: 'S82'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---

# Author and hand-review the Modelo 390 2025 exact-source semantic map and exhaustive source-bound render profile, bijecting all 612 numbered-page fixed anchors plus the separately governed 13-anchor auxiliary header for 625 parsed anchors total by carrying the 2025 revision's 477 exact layout owners and 119 exact binding owners, explicitly classifying 16 reserved fillers, preserving the payloads of all 523 parser-stable anchors, reviewing all 89 changed common anchors, removing the nine retired Page 5 rows, and proving the three retired Page 5 slots at A27, A51 and A101 are explicit fillers before the nine numbered-record composition renders

## Scope

- `dev/registry/mappings/modelo_390/2025/`
- `dev/registry/render_profiles/modelo_390/2025/`
- `dev/registry/tests/test_m390_2025_semantic_map.py`

## Changes

- `A` `dev/registry/mappings/modelo_390/2025/0001-records.toml`
- `A` `dev/registry/mappings/modelo_390/2025/0002-entries.toml`
- `A` `dev/registry/render_profiles/modelo_390/2025/0001-numeric-representation.toml`
- `A` `dev/registry/tests/test_m390_2025_semantic_map.py`
- `M` `.vault/plan/2026-08-10-aeat-export-fragment-generator-authority-plan.md`
- `A` `.vault/audit/2026-09-07-aeat-export-fragment-generator-authority-s82-semantic-map-review-audit.md`
- `M` `.vault/index/aeat-export-fragment-generator-authority.index.md`
- `verify:` `uv run --no-sync pytest -q dev/registry/tests/test_m390_2025_semantic_map.py` -> `pass (2 passed)`
- `verify:` `uv run --no-sync basedpyright dev/registry/tests/test_m390_2025_semantic_map.py` -> `pass (0 errors, 0 warnings, 0 notes)`
- `verify:` `uv run --no-sync ruff check dev/registry/tests/test_m390_2025_semantic_map.py` -> `pass`
- `verify:` `uv run --no-sync ruff format --check dev/registry/tests/test_m390_2025_semantic_map.py` -> `pass`

## Notes

The feature-wide Vaultspec check is externally red because the concurrently
edited `.vault/adr/2026-08-11-tui-interface-adr.md` is not valid UTF-8 at byte
12671 and is therefore excluded from global metadata scans. S82 does not touch
that file. Its feature annotations and all other reported feature checks are
clean; the four pre-existing body-section warnings and intentional `PLAN022`
ordering warning remain unchanged.
