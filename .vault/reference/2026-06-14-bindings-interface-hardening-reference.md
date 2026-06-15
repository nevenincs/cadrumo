---
tags:
  - '#reference'
  - '#bindings-interface-hardening'
date: '2026-06-14'
modified: '2026-06-15'
related:
  - "[[2026-06-14-bindings-interface-hardening-adr]]"
  - "[[2026-06-14-bindings-interface-hardening-research]]"
---



# `bindings-interface-hardening` reference: `bindings interface code anchors: validator dispatch, selector models, carrier and CLI payloads`

Concrete current-state code anchors the implementation steps edit. Every anchor
was confirmed by `Read`/`rg` during the swarm discovery. Line numbers are HEAD at
discovery time and MUST be re-confirmed immediately before each edit (the shared
factory branch lands peer commits continuously).

## Summary

### Schema and dispatch (cluster A, B)

- `src/aeat/domain/calculations/registry/_schema.py:977-1004` — `DataBindingDefinition`
  (`id`, `source` 18-member Literal `:979-997`, `selector` `:998`, free-form
  `aggregation` `:999`, dead `typed_enum` `:1000`, `legal_refs`/`source_refs`
  `:1001-1004`).
- `src/aeat/domain/calculations/registry/_bindings.py:535-558` —
  `_BINDING_SELECTOR_REGISTRY` (selector-model dispatch table).
- `_bindings.py:561-610` — `validate_binding_selector_shape`; counterpart/withholding
  build-time lift at `:591-592` and `:605-609`.
- `src/aeat/domain/calculations/registry/_binding_selector_utils.py:15-20` —
  `selector_as_dict` normalisation.
- Per-family modules: `_counterpart_bindings.py` (`_validated_counterpart_selector`
  `:123`; resolvers `:186-263`), `_invoice_bindings.py`
  (`validate_invoice_binding_definition`; resolvers `:307-391`),
  `_ledger_bindings.py` (`LEDGER_BINDING_SOURCE_KINDS` incomplete `:32`; selectors
  `target_casilla` shape divergence `:484` vs `:576`; IVA screen `:381-428`),
  `_withholding_bindings.py` (`validate_withholding_binding_selector_shape ->
  list[str]` `:124-127`), `_detail_record_bindings.py` (resolve-only
  `_validated_*_selector` `:85,214,349,456`), `_bindings_previous_filing.py`
  (`_aggregate_previous_filing_binding` op check at resolve `:379-395`).
- Source-kind enums: `src/aeat/core/aggregation.py` — `AggregationSourceKind`
  `:13-30`, `COUNTERPART_SOURCE_KINDS` `:41-48`, `RowSetGroupingKind` `:79-92`
  (half-adopted: `RELATED_PARTY`/`ATRIBUCION`/`REFUND` enum members unused as source
  tokens).

### Resolution / mesh (settled; cluster C residuals only)

- `src/aeat/application/aggregation/_source_mesh.py` — `ModeloSourceResolver`
  protocol `:212-232`, `CalculationSourceResolution` `:120-209`,
  `merge_source_resolutions` `:235-288`, `DEFERRED_SOURCE_KINDS` `:65-73`,
  `collect_unhandled_source_diagnostics` `:291-317`.
- `src/aeat/application/modelo/_calculation_actions.py` — mesh assembly
  `:534-578`, `_BUCKET_AGGREGATION_OWNED_SOURCES` `:129-144`,
  `assert_no_novel_source_kinds` `:875-903` (live `:691`), unhandled diagnostics
  live `:587-595`.
- R2 carry-gate triplication: `src/aeat/application/calculations/_binding_prefill.py:75-97`
  and `:558-561` (silent prev-filing skip); `_cross_period_clean_state.py:706-740`;
  `_relation_prefill.py:164` (non-formula relation silent), `:360-365`
  (`_formula_relation_ids` filter).

### Operator boundary (cluster D)

- Carrier: `src/aeat/domain/filing/_schema.py:71-80` — `ModeloBindingValue`
  (no `legal_refs`/`source_refs`); casilla parity model `ModeloCasillaProvenance`
  `:83-98`.
- Builder: `src/aeat/application/filing/__init__.py:426-454` — hardcoded
  `source="registry binding input"`, drops binding grounding; casilla provenance
  `:235-243`.
- CLI: `src/aeat/entrypoints/cli/_modelo_discovery_cli.py` — `bindings` sub-app
  `:72-83`, `list` `:427-487` (`--modelo` untyped `:431-434`), `preview`
  `:500-596`; `_binding_list_rows_for_report` `:401-418`.
- CLI payloads: `src/aeat/entrypoints/cli/_modelo_payloads.py:825-860` —
  `BindingRowPayload` (unused) / `BindingPreviewRowPayload`;
  `ModeloBindingsListResult.bindings: list[dict[str, object]]` `:850`.
- Override parse: `src/aeat/entrypoints/cli/_modelo_cli_support.py:126-150`
  (`validate_binding_key`, value verbatim); numeric/enum heuristic
  `src/aeat/application/modelo/_calculate_input.py:214-220`.
- Export (already preserves grounding): `registry/_export.py:191-215`.

### Semantic homonyms (cluster E)

- `src/aeat/application/modelo/_profile_binding.py` — profile-fact resolution
  (keep "binding").
- `src/aeat/adapters/outbound/google/_profile_binding.py:26` — OAuth active-profile
  scoping (RENAME).
- `src/aeat/application/modelo/_decimal_binding_value.py:26` — `decimal_from_string`
  parser (RECLASSIFY).
- `src/aeat/domain/iva/tests/test_legal_basis_binding.py` — rate→BOE verification
  (RENAME concept).
- Source-resolver result types (one role, three shapes):
  `ProfileSourcedBindingResult` (`_profile_binding.py`),
  `Modelo100BorradorBindingResult` (`_borrador_binding.py:75`), IVA-wallet path
  (`_iva_wallet_gate.py:73,93`); orchestrator `_binding_resolution.py:30`.

### Prior art (do not re-decide)

- Settled mesh: `2026-05-20-calculation-source-connectivity-adr`,
  `2026-06-10-calculation-aggregation-taxonomy-adr`.
- Un-promoted codify candidates to promote: `registry-resolver-family-extraction`
  (`2026-06-02-registry-bindings-boundary-audit`), `registry-formula-runtime-facade`
  (`2026-06-02-registry-formula-runtime-boundary-audit`).
- Existing gates to honour: `assert_no_novel_source_kinds`,
  `_validate_relation_sources.py` collision gate,
  `test_pull_path_calculate_path_casilla_parity.py`,
  `test_source_resolver_enrollment.py`.
