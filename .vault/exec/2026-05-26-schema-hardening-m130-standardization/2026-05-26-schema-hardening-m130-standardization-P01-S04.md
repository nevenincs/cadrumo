---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-26'
modified: '2026-05-26'
step_id: 'S04'
related:
  - '[[2026-05-26-schema-hardening-m130-standardization-plan]]'
---

# `schema-hardening-m130-standardization` `P01.S04`

Recorded review outcome, downstream application fallout, and the next
single-file normalization edge after the M130 split.

- Created: `.vault/audit/2026-05-26-schema-hardening-m130-standardization-review.md`
- Modified: `src/aeat/application/filing/__init__.py`
- Modified: `src/aeat/application/filing/test_filing.py`
- Modified: `src/aeat/adapters/outbound/aeat/export/_formats/test_fichero_boe_roundtrip.py`

## Description

The review found no loader/schema regression and no per-modelo registry
behavior. The split did expose a real downstream application gap: draft
construction only forwarded formula-consumed bindings and did not forward
bindings attached directly to bound casillas. That was repaired generically by
including bound-casilla binding ids in the calculation binding set and
materializing calculated bound casilla values as inherited registry-binding
values.

The post-split baseline is:

- M130 has no `130.toml` single-file source.
- M130 has one fragment-directory revision source.
- Largest M130 TOML fragment: 721 lines.
- The relevant application/export tests now provide carry-forward values
  through bindings instead of manual bound-casilla inputs.

Next edge: M190 is the largest remaining single-file modelo and should be the
next standardization target unless the planned file-size/row-size creep gate
identifies a more urgent regression.

## Tests

Validation completed:

- `uv run --no-sync pytest src/aeat/application/filing/test_filing.py -q`
- `20 passed`
- `uv run --no-sync pytest src/aeat/application/filing/test_filing.py src/aeat/adapters/outbound/aeat/export/_formats/test_fichero_boe_roundtrip.py::test_modelo_130_golden_sha_fichero_boe -q`
- `21 passed in 78.92s`
- `uv run --no-sync ruff check src/aeat/application/filing/__init__.py src/aeat/application/filing/test_filing.py src/aeat/adapters/outbound/aeat/export/_formats/test_fichero_boe_roundtrip.py`
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_modelo_130_registry.py src/aeat/domain/calculations/registry/test_loader_directory_mode.py src/aeat/domain/calculations/registry/test_committed_registry.py src/aeat/domain/calculations/registry/test_referential_integrity.py src/aeat/domain/calculations/registry/test_formula_runtime.py src/aeat/domain/calculations/registry/test_registry_schema.py src/aeat/application/filing/test_filing.py src/aeat/adapters/outbound/aeat/export/_formats/test_fichero_boe_roundtrip.py::test_modelo_130_golden_sha_fichero_boe -q`
- `229 passed in 168.18s`
