---
step_id: S117
tags:
  - "#exec"
  - "#cross-domain-continuity"
date: 2026-05-27
modified: '2026-05-27'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-05-26-cross-domain-continuity-W07-P32-S116]]"
---

# cross-domain-continuity W07.P32.S117 — projection regression test

## Outcome

Regression test written, passing (1/1), lint-clean and type-clean at
`src/aeat/entrypoints/cli/test_modelo_projection.py`.

Commit: `ca0b17c30`

## What was done

Created `test_modelo_proyecto_m130_to_m100_full_year_aggregation` using the
`isolated_runtime_profile` / `TestRuntimeProfile` fixture pattern (real KEK/DEK,
real SQLite backend — no mocks, no unsecured monkeypatch).

### Test structure (non-tautological)

**Drive side**: creates 4 M130 work units (1T-4T 2024) via CLI, calculates
each with oracle inputs (ingresos=12,000, gastos=4,000 per quarter; prev-year
income=13,000 so minoración=0).  Then invokes `aeat app modelo project --year
2024 --ccaa madrid` and reads the JSON response.

**Oracle side**: calls `calculate_registry_snapshot` directly with the same
accumulated inputs (`0505=32,000`, `0604=6,400`) and the same default
bindings.  This is an independent code path: the project verb reads from
stored `CalculationRevision` records; the oracle calls the engine directly.

Per `no-tautological-calculation-tests.md` the expected M100 casilla values
come from the registry engine itself, not from a re-implementation of the
IRPF tariff formula.

### Oracle inputs (AEAT DR 130 Instrucciones authority)

| Casilla | Per-quarter | 4Q accumulated |
|---------|-------------|----------------|
| 03 rendimiento neto | 8,000 EUR | 32,000 EUR |
| 19 resultado final  | 1,600 EUR |  6,400 EUR |

Authority: AEAT DR 130 Instrucciones, Casilla 04 «20 por 100»; Casilla 19
«Resultado final»; IRPF Art. 99 (BOE-A-2006-20764); RD 439/2007 Art. 110.

### Assertions

- `quarters_filed == 4`, `is_extrapolated is False`
- Accumulated totals match oracle constants
- M100 casillas 0545, 0546, 0595, 0596, 0597 match direct engine output

## Files changed

- `src/aeat/entrypoints/cli/test_modelo_projection.py` (NEW, 297 lines)
