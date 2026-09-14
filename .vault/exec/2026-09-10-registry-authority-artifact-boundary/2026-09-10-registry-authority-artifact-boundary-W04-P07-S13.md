---
tags:
  - '#exec'
  - '#registry-authority-artifact-boundary'
date: '2026-09-12'
modified: '2026-09-12'
body_schema: 'body-v2'
body_hash: 'sha256:a249b55b97729db16ecd5e9128868243783e5c36906fcae2b5506f6f19409d66'
step_id: 'S13'
related:
  - "[[2026-09-10-registry-authority-artifact-boundary-plan]]"
---
# Compile parallel IVA, territory, recargo and authorization inputs into canonical typed registry catalogues

## Scope

- `src/cadrumo/domain/calculations/registry/schema.py`
- `dev/registry/compiler/`
- `src/cadrumo/_data/registry/aeat/`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/runtime_catalogues.py`
- `M` `dev/registry/compiler/runtime_catalogues.py`
- `M` `dev/registry/compiler/validator.py`
- `M` `dev/registry/compiler/tests/test_iva_runtime_catalogues.py`
- `verify:` `uv run --no-sync pytest -q dev/registry/compiler/tests/test_iva_runtime_catalogues.py -k "not compiler_refuses_an_unknown_legal_reference and not compiler_refuses_a_verified_quotation_absent_from_the_corpus"` -> `pass`
- `verify:` `uv run --no-sync pytest -q dev/registry/compiler/tests/test_iva_runtime_catalogues.py::test_the_compiler_refuses_a_verified_quotation_absent_from_the_corpus -n 0` -> `pass`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/domain/calculations/registry/tests/test_authority_artifact.py` -> `pass`
- `verify:` `uv run --no-sync ruff check src/cadrumo/domain/calculations/registry/runtime_catalogues.py dev/registry/compiler/runtime_catalogues.py dev/registry/compiler/validator.py dev/registry/compiler/tests/test_iva_runtime_catalogues.py` -> `pass`
