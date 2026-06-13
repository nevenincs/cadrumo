---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'S04'
related:
  - '[[2026-05-27-schema-hardening-m309-standardization-plan]]'
---



# `schema-hardening-m309-standardization` `P01.S04`

Records the Modelo 309 standardization review outcome, the post-split
reviewability baseline, and the next single-file normalization edge.

- Modified: `.vault/plan/2026-05-27-schema-hardening-m309-standardization-plan.md`
- Created: `.vault/exec/2026-05-27-schema-hardening-m309-standardization/2026-05-27-schema-hardening-m309-standardization-P01-S04.md`

## Description

The S01 inventory mapped the M309 single-file source into a 13-fragment
directory layout matching the established generic loader contract. The S02
mechanical split landed `manifest.toml` plus the
`revisions/2004-y-siguientes/` fragment tree without altering any casilla,
formula, binding, reference, schedule, construct, or completeness-manifest
content. The S03 verification confirmed directory loading, registry validity,
ad-hoc schedule behavior, ledger IVA binding resolution, and application
aggregation behavior.

Post-split reviewability baseline: 13 TOML fragments, largest 70 lines
(`application_links`), no fragment over the per-fragment reviewability
ceiling. The original `309.toml` is removed; the fragment tree is the
canonical M309 source.

The remaining root-level single-file modelos are `360.toml`, `036.toml`,
`840.toml`, and `308.toml`. `360.toml` is the largest remaining root-level
single-file modelo and is therefore the next standardization edge.

## Tests

- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_modelo_309_registry.py src/aeat/domain/calculations/registry/test_loader_directory_mode.py src/aeat/domain/calculations/registry/test_ledger_iva_aggregation_binding.py src/aeat/application/aggregation/test_iva_ledger.py::test_preclassified_candidates_feed_modelo_309_recargo_and_reverse_charge_bindings -q`
- Result: covered by the S03 verification pass (52 passed).
