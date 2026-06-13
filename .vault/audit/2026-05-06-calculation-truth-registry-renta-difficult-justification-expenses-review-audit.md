---
tags:
  - '#audit'
  - '#calculation-truth-registry'
date: '2026-05-06'
modified: '2026-05-06'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-03-calculation-truth-registry-pending-adr]]'
  - '[[2026-05-06-calculation-truth-registry-renta-difficult-justification-expenses-exec]]'
---



# `calculation-truth-registry` Code Review

No blocking issues were found in the Modelo 100 difficult-justification expense
slice.

The calculation is configuration-owned: the 5 percent rate, EUR 2,000 cap,
formula, casilla ownership, and legal/source references are all in the registry
and legal catalogue. Python only supplies generic formula evaluation and date
axis resolution.

The runtime date default is constrained to `filing_period` and derives from the
selected snapshot year. A separate negative test mutates a committed parameter
to a different date axis and proves the runtime still fails hard when that
axis is absent.

Verification recorded:

- `uv run pytest src/aeat/domain/calculations/registry/test_modelo_100_registry.py src/aeat/domain/calculations/registry/test_formula_runtime.py -q`
- `uv run ty check src/aeat/domain/calculations/registry/_formula_runtime.py src/aeat/domain/calculations/registry/_schema.py src/aeat/domain/calculations/registry/test_modelo_100_registry.py src/aeat/domain/calculations/registry/test_formula_runtime.py`
- `uv run ruff check src/aeat/domain/calculations/registry/_formula_runtime.py src/aeat/domain/calculations/registry/_schema.py src/aeat/domain/calculations/registry/test_modelo_100_registry.py src/aeat/domain/calculations/registry/test_formula_runtime.py`
- `git diff --check -- registry/aeat/modelos/100.toml registry/aeat/legal/irpf.toml corpus/normatives/rd-439-2007.json src/aeat/domain/calculations/registry/_formula_runtime.py src/aeat/domain/calculations/registry/_schema.py src/aeat/domain/calculations/registry/test_modelo_100_registry.py src/aeat/domain/calculations/registry/test_formula_runtime.py`
