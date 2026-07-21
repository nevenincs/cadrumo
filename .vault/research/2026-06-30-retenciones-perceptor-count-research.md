---
tags:
  - '#research'
  - '#retenciones-perceptor-count'
date: '2026-06-30'
modified: '2026-06-30'
related:
  - "[[2026-06-24-retenciones-perceptor-count-adr]]"
---

# `retenciones-perceptor-count` research: `RET-1 current-state source split research`

Current-state research for the RET-1 P03 closure. The work used code RAG and direct source inspection to distinguish the distinct-NIF retenciones source used by M180/M193 from the distinct-percepciones withholding source used by M190.

## Findings

### M180 and M193 are RET-1 distinct-NIF count consumers

`uvx vaultspec-rag search "M190 M111 reconciliation missing binding fact modelo-111-trabajo-dinerario-perceptores test helper" --type code` and direct registry inspection show M180 and M193 bind their annual perceptor totals to `source = "retenciones_aggregation"` with `fact = "perceptor_count_distinct"`. The resolver implementation in `src/aeat/application/aggregation/_modelo_bindings.py` maps M180 and M193 to the validated retenciones aggregation primitives.

### M190 is intentionally not a retenciones_aggregation consumer

`uvx vaultspec-rag search "M190 percepciones withholding source resolver not retenciones_aggregation" --type code` returned the load-bearing split: `RetencionesAggregationSourceResolver` documents that M190 is not included because its annual header is a "percepciones" count, while `WithholdingSourceResolver` materialises the distinct `(perceptor, clave, subclave)` count. The M190 registry binding `modelo-190-percepciones-anual` uses `source = "withholding"` and `fact = "percepcion_count"`.

### M190 reconciliation fixture needed to follow the M111 bound-source contract

The failing verification exposed test drift rather than a production source error. M111 now binds 01/02/03 through `retenciones_aggregation`; the reconciliation helper was still resolving bound inputs with an empty binding-value map and then overlaying manual casilla inputs. The fixture now builds typed `RetencionObservation` rows, runs `aggregate_retenciones_111`, resolves binding values through `resolve_retenciones_aggregation_binding_values`, and leaves only unbound zero casillas as manual inputs.

### Verification evidence

- M190 focused set: `uv run --no-sync pytest -q --tb=short src/aeat/application/calculations/tests/test_modelo_190_111_reconciliation_continuity.py src/aeat/application/aggregation/tests/test_withholding_source_resolver.py src/aeat/application/calculations/tests/test_modelo_190_percepciones_e2e.py src/aeat/domain/calculations/registry/tests/test_withholding_percepcion_count.py` passed with 12 tests.
- M180/M193 retenciones set: `uv run --no-sync pytest -q --tb=short src/aeat/application/calculations/tests/test_modelo_180_115_reconciliation_continuity.py src/aeat/application/calculations/tests/test_modelo_193_123_reconciliation_continuity.py src/aeat/application/aggregation/tests/test_retenciones_aggregation_resolver.py` passed with 14 tests.
- Store/enrollment set: `uv run --no-sync pytest -q --tb=short src/aeat/application/aggregation/tests/test_retencion_observations_repository_roundtrip.py src/aeat/application/aggregation/tests/test_retenciones.py src/aeat/application/aggregation/tests/test_source_resolver_enrollment.py` passed with 33 tests.
