---
tags:
  - '#exec'
  - '#facts-registry'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:1f724dac27f5f44040a3653e1a6a271c195e3b760ab9d51265c97be380950bc5'
step_id: 'S57'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---
# Delete the obsolete IVA-rate resource repository after authority-backed rate resolution, while retaining IVA-local grounding only until the raw legal IVA tables have typed fact replacements

## Scope

- `src/cadrumo/core/resources/_repos/iva_rate_tables.py and src/cadrumo/core/resources/registry.py and dev/registry/analysis and dev/registry/tests`

## Changes

- `M` `dev/registry/analysis/facts_iva_retirement.toml`
- `D` `src/cadrumo/core/resources/_repos/iva_rate_tables.py`
- `M` `src/cadrumo/core/resources/_repos/tests/test_singletons.py`
- `M` `src/cadrumo/core/resources/registry.py`
- `M` `src/cadrumo/core/resources/tests/test_registry.py`
- `verify:` `uv run --no-sync ruff check src/cadrumo/core/resources/_repos/iva_rate_tables.py src/cadrumo/core/resources/registry.py src/cadrumo/core/resources/_repos/tests/test_singletons.py src/cadrumo/core/resources/tests/test_registry.py dev/registry/analysis/facts_iva_retirement.toml` -> `pass`
- `verify:` `uv run --no-sync pytest -q dev/registry/tests/test_iva_rate_provider.py dev/registry/tests/test_iva_structured_table_classification.py` -> `pass`

## Notes

- `_grounding.py` remains only while `place_of_supply.py` and `establishment.py` resolve the four retained raw legal IVA tables; S85 requires their typed fact migrations and equivalent authority evidence refusal before deleting it.
- Wider resource tests have a pre-existing stale `topics` import/expectation and the missing published authority artifact; neither is a rate-repository fallback.
