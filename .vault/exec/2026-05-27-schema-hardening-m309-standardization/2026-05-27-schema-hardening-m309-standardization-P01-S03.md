---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-27'
step_id: 'S03'
related:
  - '[[2026-05-27-schema-hardening-m309-standardization-plan]]'
---

<!-- DO NOT add 'Related:', 'tags:', 'date:', or other frontmatter fields
     outside the YAML frontmatter above -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline `code`. -->

# `schema-hardening-m309-standardization` `P01.S03`

Verified the Modelo 309 directory-fragment layout against the focused
registry, loader, IVA aggregation, and application aggregation surfaces.

- Modified: `.vault/plan/2026-05-27-schema-hardening-m309-standardization-plan.md`
- Created: `.vault/exec/2026-05-27-schema-hardening-m309-standardization/2026-05-27-schema-hardening-m309-standardization-P01-S03.md`

## Description

The verification confirmed Modelo 309 loads from the directory-fragment
layout with the same ad-hoc revision metadata, workbook parity reference,
verification expectation, ledger IVA bindings, casillas, formula,
live cross-reference guard surfaces, application links, filing schedule,
construct membership, and completeness manifest.

Reviewability baseline after the split:

- `309.toml` no longer exists.
- Modelo 309 has 13 TOML fragments.
- Largest Modelo 309 fragment: 70 lines (`application_links`).
- No Modelo 309 fragment exceeds the reviewability ceiling.

## Tests

- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_modelo_309_registry.py src/aeat/domain/calculations/registry/test_loader_directory_mode.py src/aeat/domain/calculations/registry/test_ledger_iva_aggregation_binding.py src/aeat/application/aggregation/test_iva_ledger.py::test_preclassified_candidates_feed_modelo_309_recargo_and_reverse_charge_bindings -q`
- Result: 52 passed in 118.05 s.
