---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'S04'
related:
  - '[[2026-05-27-schema-hardening-m184-standardization-plan]]'
---



# `schema-hardening-m184-standardization` `P01.S04`

Recorded the M184 review outcome, final standardization baseline, and next
single-file normalization edge.

- Modified: `.vault/plan/2026-05-27-schema-hardening-m184-standardization-plan.md`
- Created: `.vault/audit/2026-05-27-schema-hardening-m184-standardization-review.md`
- Created: `.vault/exec/2026-05-27-schema-hardening-m184-standardization/2026-05-27-schema-hardening-m184-standardization-P01-S04.md`
- Created: `.vault/exec/2026-05-27-schema-hardening-m184-standardization/2026-05-27-schema-hardening-m184-standardization-P01-summary.md`

## Description

The final review found no stale `184.toml` sibling and confirmed that the
layout split itself reconstructs the pre-split source exactly. The review also
found a later committed semantic change to M184's `declaracion_pdf` extraction
profile in `13f5e39db`. That cross-campaign profile grounding work is outside
the mechanical split and was preserved.

Final M184 layout baseline:

- `184.toml` does not exist.
- One fragment-directory revision exists: `2015-y-siguientes`.
- Modelo 184 has 13 TOML fragments.
- Largest Modelo 184 fragment: 95 lines.
- Largest remaining root-level single-file modelo: `193.toml` at 472 lines.

## Tests

- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_modelo_184_registry.py src/aeat/domain/calculations/registry/test_loader_directory_mode.py -q`
- Result: 32 passed.

- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_modelo_184_registry.py src/aeat/domain/calculations/registry/test_loader_directory_mode.py src/aeat/domain/calculations/registry/test_committed_registry.py src/aeat/domain/calculations/registry/test_referential_integrity.py src/aeat/domain/calculations/registry/test_detail_record_row_builders.py src/aeat/domain/calculations/registry/test_detail_record_modelo_coverage.py src/aeat/application/calculations/test_row_set_assembly.py src/aeat/application/calculations/test_detail_record_round_trip.py -q`
- Result: 157 passed.

- Current HEAD rerun including `13f5e39db` profile grounding and parser-boundary coverage: 256 passed.

- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-05-27-schema-hardening-m184-standardization-plan.md`
- Result: passed.
