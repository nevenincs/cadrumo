---
tags:
  - "#exec"
  - "#declaracion-extraction-architecture"
date: "2026-05-28"
modified: '2026-05-28'
step_id: "S204"
related:
  - "[[2026-05-21-declaracion-extraction-architecture-plan]]"
  - "[[2026-05-21-declaracion-extraction-architecture-adr]]"
---

# declaracion-extraction-architecture W10.P47.S204 — M180 M115 cross-modelo relation binding

## Audit finding

The Phase 2 verification chain commit (7193ef4f8) documented M180 as BINDING-GAP for engine
verification because `test_verification_chain_m180_parser_extracts_declaracion_pdf_casillas`
exercised extraction only. The M115→M180 TOML binding structure (relations/ and bindings/) was
already present in both revisions (2019-2022 and 2023-y-siguientes) from the fragmentation
commit 184cf9093.

The actual gap: no test in `test_verification_chain.py` exercised the full engine path by
supplying M115 quarterly `relation_values` to `calculate_registry_snapshot` for M180.

## Resolution

Added `test_verification_chain_m180_engine_recomputes_closure_casillas_from_m115_relation_values`
to `src/aeat/adapters/inbound/declaracion/test_verification_chain.py`.

Chain exercised:
1. Parse 2024-0A M180 fixture (Orden HAP/1732/2014 synthetic PDF) → extract 3 closure casillas
2. Build 4 M115 quarterly RegistryModeloObservation instances for 2024:
   - Q1-Q3 casilla 01=1, 02=3000.00, 03=570.00
   - Q4    casilla 01=0, 02=3000.00, 03=570.00
   - Sums: 01=3, 02=12000.00, 03=2280.00 — consistent with M180 fixture totals
3. `resolve_relation_values_from_observations` → resolves 3 relation keys:
   modelo-180-rel-115-perceptores-anual, modelo-180-rel-115-base-anual,
   modelo-180-rel-115-retenciones-anual
4. `calculate_registry_snapshot(snapshot, inputs={}, relation_values=...)` on M180 2023-y-siguientes
5. Assert engine values == extracted values for all 3 closure casillas

Also added the missing imports (`CasillaObservation`, `RegistryModeloObservation`,
`resolve_relation_values_from_observations`) to the test module.

## Verdict

**M180 VERIFIED** — engine recomputes all 3 closure casillas from supplied M115 quarterly
relation_values. The existing TOML binding structure was structurally complete; the gap was
a missing end-to-end engine test.

## Test results

```
test_verification_chain_m180_engine_recomputes_closure_casillas_from_m115_relation_values PASSED
test_verification_chain_m180_parser_extracts_declaracion_pdf_casillas PASSED
32 passed in 105.75s (full verification chain suite)
1 passed — test_modelo_parity_coverage (26 modelos valid)
```

## Files changed

- `src/aeat/adapters/inbound/declaracion/test_verification_chain.py`
  — added engine verification test + 3 new imports
