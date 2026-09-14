---
tags:
  - '#exec'
  - '#registry-authority-artifact-boundary'
date: '2026-09-12'
modified: '2026-09-12'
body_schema: 'body-v2'
body_hash: 'sha256:f4e9803ee48f2b4cbca9c02e6d9ca4b81f8dbd706bbef1e45bbc5a0acc529d07'
step_id: 'S12'
related:
  - "[[2026-09-10-registry-authority-artifact-boundary-plan]]"
---
# Implement the compact atomic v4 authority wire contract with exact typed reconstruction and no runtime delta interpreter

## Scope

- `src/cadrumo/domain/calculations/registry/authority_artifact.py`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/authority_artifact.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_authority_artifact.py`
- `M` `dev/registry/tests/test_authority_artifact_round_trip.py`
- `M` `dev/registry/pipeline/cli.py`
- `M` `dev/packaging/tests/test_installed_oracles.py`
- `M` `src/cadrumo/_data/registry/authority/authority.json`
- `verify:` `uv run --no-sync ruff check src/cadrumo/domain/calculations/registry/authority_artifact.py src/cadrumo/domain/calculations/registry/tests/test_authority_artifact.py dev/registry/pipeline/cli.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/domain/calculations/registry/tests/test_authority_artifact.py` -> `pass`
- `verify:` `uv run --no-sync python -c "from cadrumo.domain.calculations.registry.authority import bundled_authority; a=bundled_authority(); print(len(a.modelos), len(a.catalogues.facts.facts))"` -> `pass`
- `verify:` `uv run --no-sync python -m dev.registry.pipeline --help` -> `pass`
