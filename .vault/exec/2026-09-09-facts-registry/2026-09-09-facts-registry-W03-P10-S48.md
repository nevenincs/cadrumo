---
tags:
  - '#exec'
  - '#facts-registry'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:e0ccf1c940c525cc2ffc0584176663d5aa8c71f890dfcd73d142ef570f8c19df'
step_id: 'S48'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---

# Rewire every M347 comparator validator and diagnostic to one fact

## Scope

- `src/cadrumo/domain/calculations/registry/_m347_threshold.py and dependent production callers`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/_m347_threshold.py`
- `M` `src/cadrumo/domain/calculations/registry/invoice_bindings.py`
- `M` `src/cadrumo/application/aggregation/_counterpart.py`
- `M` `src/cadrumo/application/invoices/source_resolver.py`
- `M` `src/cadrumo/application/modelo/calculate_input.py`
- `M` `src/cadrumo/domain/modelos/row_models.py`
- `M` `src/cadrumo/domain/modelos/tests/test_row_models_m347_revision.py`
- `M` `.vault/plan/2026-09-09-facts-registry-plan.md`
- `A` `.vault/exec/2026-09-09-facts-registry/2026-09-09-facts-registry-W03-P10-S48.md`
- `verify:` `uv run pytest src/cadrumo/domain/modelos/tests/test_row_models_m347_revision.py src/cadrumo/application/aggregation/tests/test_counterpart_347_cross_cohort_merge.py src/cadrumo/application/invoices/tests/test_source_resolver.py -q` -> `pass`
- `verify:` `uv run pytest src/cadrumo/entrypoints/cli/tests/test_work_calculate_row_flag.py src/cadrumo/application/filing/tests/test_modelo_347_contraparte_export_parity.py -q` -> `pass`
- `verify:` `uv run basedpyright src/cadrumo/domain/calculations/registry/_m347_threshold.py src/cadrumo/domain/calculations/registry/invoice_bindings.py src/cadrumo/domain/modelos/row_models.py src/cadrumo/application/aggregation/_counterpart.py src/cadrumo/application/invoices/source_resolver.py src/cadrumo/application/modelo/calculate_input.py` -> `pass`
