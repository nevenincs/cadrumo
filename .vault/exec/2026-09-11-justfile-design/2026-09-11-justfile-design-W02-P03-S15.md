---
tags:
  - '#exec'
  - '#justfile-design'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:1c5eb1bcda5a0e80d3dee2630ea3c9dbc5c0320089026be69be279d598547d8e'
step_id: 'S15'
related:
  - "[[2026-09-11-justfile-design-plan]]"
---

# Move regulatory-literal validation into the registry validation owner and delegate the former module during migration

## Scope

- `dev/registry/validation`

## Changes

- `A` `dev/registry/validation/regulatory_literals.py`
- `D` `dev/quality/modelo_regulatory_literals.py`
- `D` `dev/registry/analysis/modelo_regulatory_literal_scan.py`
- `M` `dev/registry/tests/test_governed_literal_discovery.py`
- `M` `dev/registry/tests/test_modelo_regulatory_literal_scan.py`
- `M` `justfile`
- `verify:` `uv run --no-sync python -m dev.registry.validation.regulatory_literals` -> `pass`
