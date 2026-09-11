---
tags:
  - '#exec'
  - '#justfile-design'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:685f66040a46335bae9b3c78f5686a1577bd201e91f79c3bceac34470a281185'
related:
  - "[[2026-09-11-justfile-design-plan]]"
---

# `justfile-design` `W02.P03` summary

## Changes

- `A` `dev/registry/analysis/registry_status.py`
- `A` `dev/registry/conformance/tests/test_lifecycle_cli.py`
- `A` `dev/registry/validation/__init__.py`
- `A` `dev/registry/validation/regulatory_embeds.py`
- `A` `dev/registry/validation/regulatory_literals.py`
- `D` `dev/quality/modelo_regulatory_embeds.py`
- `D` `dev/quality/modelo_regulatory_literals.py`
- `D` `dev/registry/analysis/modelo_embed_scan.py`
- `D` `dev/registry/analysis/modelo_regulatory_literal_scan.py`
- `M` `dev/registry/analysis/generated_tree_state.py`
- `M` `dev/registry/conformance/cli.py`
- `M` `dev/registry/pipeline/cli.py`
- `M` `dev/registry/pipeline/render_check.py`
- `M` `dev/registry/tests/test_governed_literal_discovery.py`
- `M` `dev/registry/tests/test_modelo_regulatory_literal_scan.py`
- `M` `dev/registry/tests/test_modelo_specific_embed_scan.py`
- `M` `justfile`
- `verify:` `uv run --no-sync pytest -q --confcutdir=dev/registry/conformance/tests dev/registry/conformance/tests/test_lifecycle_cli.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.registry.conformance valid --json` -> `pass`
- `verify:` `uv run --no-sync python -m dev.registry.conformance runtime-load --json` -> `pass`
- `verify:` `uv run --no-sync python -m dev.registry.pipeline.render_check 296 2024-y-siguientes --check` -> `pass`
- `verify:` `uv run --no-sync python -m dev.registry.validation.regulatory_literals` -> `pass`
- `verify:` `uv run --no-sync python -m dev.registry.validation.regulatory_embeds` -> `fail`

## Notes

- The relocated regulatory-embed validator reproduces 22 pre-existing findings.
- The live generated-state report excludes 95 of 128 revisions as unreadable; the report preserves this as an explicit non-currentness fact.
