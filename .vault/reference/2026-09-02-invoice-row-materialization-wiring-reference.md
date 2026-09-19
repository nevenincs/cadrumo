---
tags:
  - '#reference'
  - '#invoice-row-materialization-wiring'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:be5a3aafc4d9d94b057569e1c2a857b4f0b6bfaca29146cfb2be9cd8bb9003ed'
related:
  - "[[2026-08-06-invoice-canonical-structure-adr]]"
  - "[[2026-08-24-modelo-edit-contract-adr]]"
  - "[[2026-08-26-tui-architecture-modelo-347-contraparte-binding-inventory-reference]]"
---
# `invoice-row-materialization-wiring` reference: `invoice row runtime handoff`

## Summary

The registry and renderer already implement the M347 contraparte and M349 rectificacion row families, but the invoice source resolver does not deliver both families to the calculation revision. M347 is a direct carrier omission: invoice observations can resolve its row bindings, yet `InvoiceCatalogueSourceResolver.resolve` returns only scalar `binding_values` and M349 operador `detail_rows`. M349 manual rectification rows are fully replayable, so the broad claim that rectification export is absent is false; the narrower invoice-derived claim is true because the resolver constructs neither rectification observations nor rectification detail rows.

### The live handoff has two row carriers

`InvoiceCatalogueSourceResolver.resolve` builds observations and scalar values at `src/cadrumo/application/invoices/source_resolver.py:229-255`. Its result has no `row_binding_values=` argument. The calculation mesh would preserve that channel: `calculate_modelo_revision_from_bucket_aggregation_with_diagnostics` passes `channels.source_resolution.row_binding_values` at `src/cadrumo/application/modelo/calculation_actions.py:1453-1491`, and persistence stores the normalized replay payload at `src/cadrumo/application/modelo/calculation_actions.py:533-599`.

Export replays both persisted carriers. `revision_filing_replay_inputs` merges `revision.row_binding_values` followed by projected M349 `detail_rows` at `src/cadrumo/application/modelo/_revision_replay_inputs.py:77-116`. `build_draft` converts indexed input mappings to binding values with a `row_index` at `src/cadrumo/application/filing/draft_construction.py:720-765`. A record with `repeat = "binding_rows"` derives occurrences only from active indexed binding values at `src/cadrumo/application/filing/record_renderer.py:162-228`.

### M347 contraparte rows stop inside the source resolver

Both M347 revisions declare contraparte row bindings and a repeating declarado record, for example `src/cadrumo/_data/registry/aeat/modelos/347/revisions/2025-y-siguientes/bindings/0002-contraparte-clave.toml:30-162` and `src/cadrumo/_data/registry/aeat/modelos/347/revisions/2025-y-siguientes/export/0002-record-m347-declarado.toml:5-11`. The domain resolver returns indexed values for every invoice row family at `src/cadrumo/domain/calculations/registry/invoice_bindings.py:694-721`.

The application resolver calls that domain function only inside `_m349_operador_rows_from_observations`, which rejects every non-M349 context and then retains only `_M349_OPERADOR_ROW_BINDINGS`: `src/cadrumo/application/invoices/source_resolver.py:89-95` and `src/cadrumo/application/invoices/source_resolver.py:914-960`. Thus an M347 calculation receives the scalar declarante summary but no indexed contraparte carrier. The existing M347 export parity test bypasses this missing handoff by calling `resolve_invoice_binding_row_values` and `_record_render_rows` directly, as its module contract states at `src/cadrumo/application/filing/tests/test_modelo_347_contraparte_export_parity.py:1-32`; it proves the two endpoint mechanisms, not the live join.

### M349 rectification support is present on the manual path and absent on the invoice-derived path

The registry declares eight public rectification row bindings at `src/cadrumo/_data/registry/aeat/modelos/349/revisions/2020-y-siguientes/bindings/0001-bindings.toml:120-217`, and the rectification export record repeats by binding rows at `src/cadrumo/_data/registry/aeat/modelos/349/revisions/2020-y-siguientes/export_layouts/0004-record-rectificacion.toml:5-12`. The domain invoice-row resolver can produce these bindings; the focused committed-registry proof is `src/cadrumo/domain/calculations/registry/tests/test_modelo_349_registry_bindings.py:478-525`.

Manual `Modelo349RectificacionRow` persistence and export replay are implemented. `_m349_detail_row_replay_inputs` enumerates both operador and rectification rows and maps every rectification field at `src/cadrumo/application/modelo/_revision_replay_inputs.py:245-284`; its focused proof is `src/cadrumo/application/modelo/tests/test_revision_replay_inputs.py:267-294`.

Invoice-derived rectifications do not reach that path. `_invoice_observation` emits party, date, base, total, and clave but never `is_rectification`, `rectified_year`, `rectified_period`, or `rectified_base_previous`: `src/cadrumo/application/invoices/source_resolver.py:659-689`. The canonical `Invoice` records `invoice_class` and `rectifies_invoice_number`, but not the rectified filing period or previous declared base: `src/cadrumo/domain/invoices/models.py:236-245` and `src/cadrumo/domain/invoices/models.py:336`. Finally, `_m349_operador_rows_from_observations` has no rectification binding map or `Modelo349RectificacionRow` construction branch at `src/cadrumo/application/invoices/source_resolver.py:914-960`.

### Current tests make the disconnected capability look greener than it is

The domain tests prove row grouping and the application replay test proves a manually supplied rectification row, while the invoice source test proves only ordinary operador rows at `src/cadrumo/application/invoices/tests/test_source_resolver.py:727-767`. Its declarable-fact guard explicitly classifies all four rectification axes as non-declarable at `src/cadrumo/application/invoices/tests/test_source_resolver.py:1876-1897`. There is no focused gate that starts with a secure-store invoice catalogue, runs bucket aggregation, inspects the persisted revision, and renders either an M347 contraparte row or an invoice-derived M349 rectification row.

### Governing intent

The accepted canonical-invoice decision requires capability conservation and specifically names M347 per-party totals and M349 operator rows, but does not decide M349 rectification evidence semantics: `2026-08-06-invoice-canonical-structure-adr`, decisions D-C and D-R. The accepted Modelo edit contract defines typed repeated-row intents and immutable revision persistence but does not choose the source carrier for invoice-derived rows: `2026-08-24-modelo-edit-contract-adr`, decisions D4 and D6. The M347 binding inventory records the row family and its earlier lack of a live export consumer: `2026-08-26-tui-architecture-modelo-347-contraparte-binding-inventory-reference`, lines 220-279. These documents constrain a new ADR; none authorizes silently inferring missing rectification facts.
