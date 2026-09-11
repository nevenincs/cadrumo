---
tags:
  - '#exec'
  - '#justfile-design'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:efef01d05eee4b4cdd3ebc652530b740ebbff8212ca0cfabeddd0c9e4120665b'
step_id: 'S16'
related:
  - "[[2026-09-11-justfile-design-plan]]"
---

# Move regulatory-embed validation into the registry validation owner and delegate the former module during migration

## Scope

- `dev/registry/validation`

## Changes

- `A` `dev/registry/validation/regulatory_embeds.py`
- `D` `dev/quality/modelo_regulatory_embeds.py`
- `D` `dev/registry/analysis/modelo_embed_scan.py`
- `M` `dev/registry/tests/test_modelo_specific_embed_scan.py`
- `M` `justfile`
- `verify:` `uv run --no-sync python -m dev.registry.validation.regulatory_embeds` -> `fail`

## Notes

- The relocated validator reproduces 22 pre-existing findings.
