---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-26'
modified: '2026-05-26'
related:
  - '[[2026-05-26-schema-hardening-m130-standardization-plan]]'
---

# `schema-hardening-m130-standardization` `P01` summary

Completed the M130 generic directory-fragment standardization slice.

- Modified: `src/aeat/_data/registry/aeat/modelos/130`
- Modified: `src/aeat/domain/calculations/registry/test_modelo_130_registry.py`
- Modified: `src/aeat/domain/calculations/registry/test_committed_registry.py`
- Modified: `src/aeat/domain/calculations/registry/test_formula_runtime.py`
- Modified: `src/aeat/domain/calculations/registry/test_registry_schema.py`
- Modified: `src/aeat/application/filing/__init__.py`
- Modified: `src/aeat/application/filing/test_filing.py`
- Modified: `src/aeat/adapters/outbound/aeat/export/_formats/test_fichero_boe_roundtrip.py`
- Created: `.vault/audit/2026-05-26-schema-hardening-m130-standardization-inventory.md`
- Created: `.vault/audit/2026-05-26-schema-hardening-m130-standardization-review.md`

## Description

Modelo 130 now uses the generic `manifest.toml` plus
`revisions/2019-y-siguientes` fragment-directory layout. The split removed the
largest remaining single-file modelo without changing registry schema semantics,
loader behavior, or adding model-specific definitions.

Verification repaired stale assumptions that M130 lived in `130.toml` and that
bound carry-forward casillas could be supplied as manual inputs. The application
layer was hardened so bound-casilla bindings are forwarded and materialized
generically during draft construction.

## Tests

Verification passed:

- M130 registry snapshot tests: 2 passed.
- Loader directory-mode tests: 23 passed.
- Registry verification slice: 208 passed.
- Application filing tests: 20 passed.
- Final combined M130/application/export slice: 229 passed.
- Ruff passed for the touched registry, application, and export test files.
