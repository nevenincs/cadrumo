---
tags:
  - '#exec'
  - '#aeat-export-fragment-generator-authority'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:2c8e782cbb5b5db97dac7f6a941eed8963e7287091d40faacc86a2f10e58ea95'
step_id: 'S80'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---

# Author and hand-review the Modelo 390 2023 exact-source semantic map and exhaustive source-bound render profile, bijecting all 541 numbered-page fixed anchors plus the separately governed 13-anchor auxiliary header for 554 parsed anchors total, reusing only unchanged source-anchor and owner adjudications and hand-reviewing every delta, and explicitly adjudicate the recurring hash-pinned 2023 Page 7 close-literal source defect through the accepted pipeline catalogue so the complete render remains exact

## Scope

- `dev/registry/mappings/modelo_390/2023/`
- `dev/registry/render_profiles/modelo_390/2023/`
- `dev/registry/pipeline/source_defects.py`
- `dev/registry/tests/test_source_defect_declarations.py`
- `dev/registry/tests/test_m390_2023_semantic_map.py`

## Changes

- `A` `dev/registry/mappings/modelo_390/2023/0001-records.toml`
- `A` `dev/registry/mappings/modelo_390/2023/0002-entries.toml`
- `A` `dev/registry/render_profiles/modelo_390/2023/0001-numeric-representation.toml`
- `M` `dev/registry/pipeline/source_defects.py`
- `M` `dev/registry/tests/test_source_defect_declarations.py`
- `A` `dev/registry/tests/test_m390_2023_semantic_map.py`
- `M` `.vault/plan/2026-08-10-aeat-export-fragment-generator-authority-plan.md`
- `A` `.vault/audit/2026-09-07-aeat-export-fragment-generator-authority-s80-semantic-map-review-audit.md`
- `M` `.vault/index/aeat-export-fragment-generator-authority.index.md`
- `verify:` `uv run --no-sync pytest -q dev/registry/tests/test_m390_2023_semantic_map.py dev/registry/tests/test_source_defect_declarations.py` -> `pass (18 passed)`
- `verify:` `uv run --no-sync basedpyright dev/registry/tests/test_m390_2023_semantic_map.py dev/registry/pipeline/source_defects.py dev/registry/tests/test_source_defect_declarations.py` -> `pass (0 errors, 0 warnings, 0 notes)`
- `verify:` `uv run --no-sync ruff check dev/registry/tests/test_m390_2023_semantic_map.py dev/registry/pipeline/source_defects.py dev/registry/tests/test_source_defect_declarations.py` -> `pass`
- `verify:` `uv run --no-sync ruff format --check dev/registry/tests/test_m390_2023_semantic_map.py dev/registry/pipeline/source_defects.py dev/registry/tests/test_source_defect_declarations.py` -> `pass`
- `verify:` `uv run --no-sync vaultspec-core vault check annotations --feature aeat-export-fragment-generator-authority --json` -> `pass`

## Notes

The broader `test_m390_auxiliary_envelope.py` module cannot currently collect
because unrelated concurrent application changes introduce a
`CalculationSourceContext` circular import. Its isolated rerun failed at the
same import boundary with a stable HEAD; S80's own detector reads the real
parser intermediate directly and proves the separately governed auxiliary
header still contains 13 anchors.
