---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-04'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:539e263d35cbe7e67e034a81944d9b03759f45f6090983bfcc6e26590768e963'
step_id: 'S131'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the Modelo branch adjudication ledger and replace its authored classifications with a live zero-target structural detector for numeric regulatory policy embedded beside modelo routing

## Scope

- `development registry analysis`
- `branch detector`
- `detector-teeth tests`
- `and quality aggregation`

## Changes

- `D` `dev/registry/analysis/modelo_branch_classification.py`
- `D` `dev/registry/analysis/modelo_branch_classification.toml`
- `A` `dev/registry/analysis/modelo_regulatory_literal_scan.py`
- `D` `dev/registry/tests/test_modelo_branch_classification.py`
- `A` `dev/registry/tests/test_modelo_regulatory_literal_scan.py`
- `A` `dev/quality/modelo_regulatory_literals.py`
- `M` `dev/quality/suite.py`
- `M` `justfile`
- `verify:` `uv run ruff check <S131 Python paths>` -> `pass`
- `verify:` `rg exact retired branch-classification vocabulary across src/dev` -> `pass`

## Notes

The live zero-target gate reports one finding: `src/cadrumo/application/aggregation/_inventory.py::resolve` couples `Modelo.M100` routing to literal filing year `2025`. The focused detector suite has one detector-teeth pass and that expected live failure; the direct quality command reports the same single finding and exits 1.
