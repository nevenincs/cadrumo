---
tags:
  - '#exec'
  - '#facts-registry'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:38e40020555999e27525f695a19814ad25d22e78704178dd62a6ca4c84ef1bf2'
step_id: 'S24'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---
# Rewire maritime Art 7p and REBECA inputs

## Scope

- `src/cadrumo/domain/renta/maritime_exemption.py`

## Changes

- `M` `src/cadrumo/domain/renta/maritime_exemption.py`
- `M` `src/cadrumo/application/calculations/maritime_exemption_service.py`
- `M` `src/cadrumo/application/modelo/maritime_preview.py`
- `M` `src/cadrumo/domain/renta/tests/test_maritime_exemption.py`
- `M` `src/cadrumo/application/calculations/tests/test_maritime_exemption_service.py`
- `A` `.vault/exec/2026-09-09-facts-registry/2026-09-09-facts-registry-W03-P11-S24.md`
- `verify:` `uv run --no-sync pytest -n 0 src/cadrumo/domain/renta/tests/test_maritime_exemption.py src/cadrumo/application/calculations/tests/test_maritime_exemption_service.py -q` -> `pass`
- `verify:` `uv run --no-sync ruff check src/cadrumo/domain/renta/maritime_exemption.py src/cadrumo/application/calculations/maritime_exemption_service.py src/cadrumo/application/modelo/maritime_preview.py src/cadrumo/domain/renta/tests/test_maritime_exemption.py src/cadrumo/application/calculations/tests/test_maritime_exemption_service.py` -> `pass`
