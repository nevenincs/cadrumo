---
tags:
  - '#audit'
  - '#registry-fragmentation'
date: '2026-05-19'
modified: '2026-05-19'
related: []
---

# `registry-fragmentation` Code Review

REGISTRY-FRAGMENTATION-001 | HIGH | Filed-observation encryption still depends on ambient bucket session state
`FiledDeclaracionObservationStore.__init__` accepts `root` and `master_key_provider` but discards both at `src/aeat/adapters/outbound/aeat/sede/_observation_store.py:29`-`31`, while registry verification forwards a provider into that constructor at `src/aeat/application/registry/__init__.py:496`-`497`. The widened gate's `NoActiveBucketSessionError` is consistent with this boundary: callers must manually enter the provider context or have a CLI active-bucket session, and the store itself cannot honor the explicit provider/root contract. Make the store own or require a real active bucket/session boundary instead of silently ignoring constructor inputs.

REGISTRY-FRAGMENTATION-002 | MEDIUM | Modelo 130 carry-forward output is admitted but not verified for value parity
The registry declares `saldo-negativo-fin-periodo` as a computed Modelo 130 casilla and formula at `src/aeat/_data/registry/aeat/modelos/130.toml:314` and `src/aeat/_data/registry/aeat/modelos/130.toml:339`, and includes it in the calculation construct at `src/aeat/_data/registry/aeat/modelos/130.toml:1368`. The test now widens the computed set at `src/aeat/adapters/outbound/aeat/sede/test_declarations.py:725`, but the parity assertion still iterates only `_MODELO_130_COMPUTED_CASILLAS` at `src/aeat/adapters/outbound/aeat/sede/test_declarations.py:734`-`735`. Add an explicit expected-value assertion or document why this derived carry-forward is intentionally excluded from filed-observation parity.

REGISTRY-FRAGMENTATION-003 | MEDIUM | Modelo 123 literal-field regressions reach export runtime instead of registry validation
The failed legacy export came from `modelo-123-2019-page-number` exceeding its declared length; the current registry field is `length = 2` with `literal = "01"` at `src/aeat/_data/registry/aeat/modelos/123/revisions/2019-2023/revision.toml:369`-`373`. Add a registry validation rule that checks every literal export field fits its declared length, so a future accidental value such as a casilla id fails at registry load/validation instead of during `export_draft`.

REGISTRY-FRAGMENTATION-004 | MEDIUM | Modelo 100 relation fixtures can drift from receiver-side source requirements
The resolver correctly fail-closes when a required source filing is absent at `src/aeat/domain/calculations/registry/_relations.py:267`-`274`. The 2025 Modelo 100 registry now requires Modelo 184 period `0A` output `tipo2.renta-atribuible-importe` at `src/aeat/_data/registry/aeat/modelos/100/revisions/2025/relations/0008-renta-2025-rel-184-atribucion-actividades-economicas.toml:5`-`10`, and the fixture had to be extended at `src/aeat/adapters/outbound/aeat/sede/test_declarations.py:1544`-`1547`. Drive relation fixtures from `relation_source_requirements` or add a fixture completeness assertion so new receiver-side dependencies cannot fragment from filed-observation coverage.
