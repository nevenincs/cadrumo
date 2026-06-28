---
tags: ["#exec", "#registry-authority-flow"]
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'S28'
related:
  - '[[2026-05-20-registry-authority-flow-plan]]'
---

# `registry-authority-flow` `W05.P12.S28`

Reduced redundant committed registry loads in slow tests.

- Modified: `src/aeat/domain/calculations/registry/test_modelo_*_registry.py`
- Modified: `src/aeat/domain/calculations/registry/test_renta_escala_*_bracket_resolution.py`
- Modified: `src/aeat/application/calculations/test_iva_compensation_history.py`
- Modified: this execution record

## Description

Added real-behavior caches to no-argument committed Modelo loader helpers and
fixed year-keyed Renta escala table helpers to avoid reloading the bundled
registry for each assertion in the same module. The tests still import and load
the real committed registry; no fakes, stubs, monkeypatching, skips, or shadow
business logic were introduced.

Also updated two stale accented Modelo title assertions and rewrote the IVA
compensation carry-forward test data so the cross-codebase tautology gate no
longer detects hand-summed aggregation assertions.

## Tests

`uv run ruff check src/aeat/domain/calculations/registry
src/aeat/application/calculations/test_iva_compensation_history.py` passed.

Focused timing improvements:

- `test_modelo_303_registry.py`: 16 passed in 21.02s after caching.
- `test_modelo_184_registry.py`: 9 passed in 21.46s after caching.
- Renta escala files 95..97: 161 passed in 91.65s after caching, replacing a
  timed-out coarse slice.

The full sorted registry package chunks passed; the slowest remaining slice was
files 85..89 at 168 passed in 362.83s, which remains tracked by
`W05.P12.S29`.
