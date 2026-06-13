---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-06'
modified: '2026-05-06'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-03-calculation-truth-registry-pending-adr]]'
---



# `calculation-truth-registry` `renta difficult justification expenses`

Moved the Modelo 100 ejercicio 2025 difficult-justification expense calculation
for simplified direct estimation into the registry.

- Modified: `registry/aeat/modelos/100.toml`
- Modified: `registry/aeat/legal/irpf.toml`
- Modified: `corpus/normatives/rd-439-2007.json`
- Modified: `src/aeat/domain/calculations/registry/_formula_runtime.py`
- Modified: `src/aeat/domain/calculations/registry/_schema.py`
- Modified: `src/aeat/domain/calculations/registry/test_modelo_100_registry.py`
- Modified: `src/aeat/domain/calculations/registry/test_formula_runtime.py`

## Description

Casilla 0222 is no longer manual in the 2025 Modelo 100 registry revision. It
is computed from the simplified direct-estimation base, a registered 5 percent
parameter, and a registered EUR 2,000 cap, with legal authority from Reglamento
IRPF article 30 and source citations against the AEAT Renta manual.

The formula runtime now defaults the `filing_period` date axis from the
selected snapshot when callers omit that date context. Non-filing-period axes
still fail hard if missing.

The Modelo 100 application-link ledger also declares approval and
reconciliation as snapshot-backed surfaces.

## Tests

- `uv run pytest src/aeat/domain/calculations/registry/test_modelo_100_registry.py src/aeat/domain/calculations/registry/test_formula_runtime.py -q`
- `uv run ty check src/aeat/domain/calculations/registry/_formula_runtime.py src/aeat/domain/calculations/registry/_schema.py src/aeat/domain/calculations/registry/test_modelo_100_registry.py src/aeat/domain/calculations/registry/test_formula_runtime.py`
- `uv run ruff check src/aeat/domain/calculations/registry/_formula_runtime.py src/aeat/domain/calculations/registry/_schema.py src/aeat/domain/calculations/registry/test_modelo_100_registry.py src/aeat/domain/calculations/registry/test_formula_runtime.py`
- `git diff --check -- registry/aeat/modelos/100.toml registry/aeat/legal/irpf.toml corpus/normatives/rd-439-2007.json src/aeat/domain/calculations/registry/_formula_runtime.py src/aeat/domain/calculations/registry/_schema.py src/aeat/domain/calculations/registry/test_modelo_100_registry.py src/aeat/domain/calculations/registry/test_formula_runtime.py`
