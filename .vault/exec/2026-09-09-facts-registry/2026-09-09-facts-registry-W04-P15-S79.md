---
tags:
  - '#exec'
  - '#facts-registry'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:cf696ed2408c399d6ccf41c1feff4e08c0bf5df3e15a0101f4a4188d3a91aa81'
step_id: 'S79'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---
# Normalize and retire the treaty-override adapter without duplicating the canonical convenio catalogue

## Scope

- `src/cadrumo/_data/registry/aeat/treaties and src/cadrumo/_data/registry/aeat/facts and dev/registry/compiler/convenio.py and dev/registry/compiler/fact_providers.py and dev/registry/compiler/authority.py and dev/registry/tests`

## Changes

- `M` `dev/registry/analysis/facts_wave2_provider_handoff.toml`
- `M` `dev/registry/compiler/authority.py`
- `M` `dev/registry/compiler/convenio.py`
- `M` `dev/registry/compiler/fact_providers.py`
- `M` `dev/registry/tests/test_convenio.py`
- `A` `dev/registry/tests/test_convenio_facts.py`
- `M` `dev/registry/tests/test_fact_providers.py`
- `M` `dev/registry/tests/test_wave2_fact_provider_handoff.py`
- `D` `src/cadrumo/_data/registry/aeat/treaties/es-ar.toml`
- `D` `src/cadrumo/_data/registry/aeat/treaties/es-be.toml`
- `D` `src/cadrumo/_data/registry/aeat/treaties/es-de.toml`
- `D` `src/cadrumo/_data/registry/aeat/treaties/es-fr.toml`
- `D` `src/cadrumo/_data/registry/aeat/treaties/es-gb.toml`
- `D` `src/cadrumo/_data/registry/aeat/treaties/es-ma.toml`
- `D` `src/cadrumo/_data/registry/aeat/treaties/es-nl.toml`
- `D` `src/cadrumo/_data/registry/aeat/treaties/es-pt.toml`
- `D` `src/cadrumo/_data/registry/aeat/treaties/es-us.toml`
- `A` `src/cadrumo/_data/registry/aeat/facts/0068-convenio-override.toml`
- `verify:` `uv run --no-sync ruff check dev/registry/compiler/convenio.py dev/registry/compiler/fact_providers.py dev/registry/compiler/authority.py dev/registry/tests/test_convenio.py dev/registry/tests/test_convenio_facts.py dev/registry/tests/test_fact_providers.py dev/registry/tests/test_wave2_fact_provider_handoff.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q dev/registry/tests/test_convenio.py dev/registry/tests/test_convenio_facts.py dev/registry/tests/test_fact_providers.py dev/registry/tests/test_wave2_fact_provider_handoff.py` -> `pass`

## Notes

- A broader suite also remains blocked by the pre-existing missing published authority artifact and concurrent M210 relocation expectations; neither has a raw-treaty fallback.
