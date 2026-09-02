---
tags:
  - '#research'
  - '#invoice-row-materialization-wiring'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:56525d848982b96cc8f55f43c19eebadfd95df1268cc71b89f09a385b18a502d'
related:
  - "[[2026-08-06-invoice-canonical-structure-adr]]"
  - "[[2026-08-24-modelo-edit-contract-adr]]"
  - "[[2026-09-02-invoice-row-materialization-wiring-reference]]"
---
# `invoice-row-materialization-wiring` research: `M347 and M349 invoice row reachability`

M347 contraparte rows and invoice-derived M349 rectification rows are genuinely disconnected from the live calculate-to-export path, but for different reasons. M347 already has sufficient invoice facts and a working row resolver; its indexed values are dropped at the application resolver boundary. M349 manual rectification rows already export correctly, so that part of the analyzer claim is a misunderstanding; the invoice-derived path is the true gap and is more serious than omission because a canonical rectificativa observation defaults to `is_rectification = False`, allowing it to be grouped as an ordinary operador row. A new ADR must settle both the derived-row carrier and the authoritative source of M349 previous-period/base facts before implementation.

## Findings

### M347 is a true runtime carrier gap, not a registry or renderer gap

Both M347 revisions declare indexed contraparte bindings and a `binding_rows` declarado export record, and `resolve_invoice_binding_row_values` resolves those declarations. The application resolver nevertheless returns only scalar bindings plus an M349-only detail-row projection; it never populates `CalculationSourceResolution.row_binding_values`. The bucket calculation already forwards that field to persisted revision replay, and the renderer already derives repeated records from it. The missing join is therefore bounded to invoice source materialization rather than registry authoring or fixed-width rendering. Evidence: `src/cadrumo/application/invoices/source_resolver.py:229-255`, `src/cadrumo/application/invoices/source_resolver.py:914-960`, `src/cadrumo/domain/calculations/registry/invoice_bindings.py:694-721`, `src/cadrumo/application/modelo/calculation_actions.py:1453-1491`, `src/cadrumo/application/filing/record_renderer.py:162-228`.

The accepted M347 binding inventory anticipated this exact boundary when it recorded that no live export consumed the binding family at the time. Later parity coverage connected the domain resolver directly to the renderer, not through the calculation mesh, so it cannot prove the runtime handoff. Evidence: `2026-08-26-tui-architecture-modelo-347-contraparte-binding-inventory-reference`, lines 220-279; `src/cadrumo/application/filing/tests/test_modelo_347_contraparte_export_parity.py:1-32`.

### The broad M349 claim is wrong for manual detail rows and correct for invoice-derived rectifications

A persisted manual `Modelo349RectificacionRow` is converted into all eight indexed binding inputs and can reach the repeating rectification record. That path is explicitly covered, so changing the renderer or generic replay code would solve no observed defect. Evidence: `src/cadrumo/application/modelo/_revision_replay_inputs.py:245-284`, `src/cadrumo/application/modelo/tests/test_revision_replay_inputs.py:267-294`, `src/cadrumo/_data/registry/aeat/modelos/349/revisions/2020-y-siguientes/export_layouts/0004-record-rectificacion.toml:5-12`.

The invoice-derived path is disconnected earlier. `Invoice` records that it is a rectificativa and names the corrected invoice, but carries no rectified filing year, period, or previous declared base. `_invoice_observation` copies none of the rectification axes required by the row bindings. Since `InvoiceObservation.is_rectification` defaults to false, a rectificativa that otherwise classifies as intracommunity is presented to the row resolver as an ordinary operation and `_m349_operador_rows_from_observations` retains only operador bindings. Evidence: `src/cadrumo/domain/invoices/models.py:236-245`, `src/cadrumo/domain/invoices/models.py:336`, `src/cadrumo/domain/calculations/registry/invoice_bindings.py:138-141`, `src/cadrumo/application/invoices/source_resolver.py:659-689`, `src/cadrumo/application/invoices/source_resolver.py:914-960`.

This is not authorized by the accepted canonical-invoice ADR. That decision required conservation of the then-existing M349 operador capability and separately made rectificativas writable, but it did not define how a rectificativa supplies M349 prior-period and previous-base facts. Treating those facts as derivable now would silently create a new filing decision outside an ADR. Evidence: `2026-08-06-invoice-canonical-structure-adr`, decisions D-C, D-R, and D-T.

### Carrier choice and rectification-fact authority are separate decisions

Option A is to make `row_binding_values` the canonical carrier for every invoice-derived repeating row, while keeping `detail_rows` as the operator-authored carrier and defining an explicit collision/refusal rule. It reuses the source-mesh and renderer handoff already present and closes M347 with the smallest architectural surface. Its cost is that existing invoice-derived M349 operador rows currently persist as typed detail rows, so migration to one carrier changes edit/read behavior and must preserve row identity and provenance. Evidence: `src/cadrumo/application/aggregation/_source_mesh.py:797-813`, `src/cadrumo/application/modelo/_revision_replay_inputs.py:77-116`.

Option B is to make typed `detail_rows` the canonical durable carrier for derived and manual rows, add an M347 contraparte replay projection, and extend the M349 projection to rectifications. It aligns with the accepted edit contract's typed row intents, but it makes the application reconstruct registry binding maps per modelo and leaves the mesh's existing generic indexed-row channel unused for invoice rows. Evidence: `2026-08-24-modelo-edit-contract-adr`, decisions D4 and D6; `src/cadrumo/application/modelo/_revision_replay_inputs.py:245-284`.

Option C is to persist synchronized `row_binding_values` and typed `detail_rows` for derived rows. An accepted M184 precedent uses both carriers, but applying it here needs an enforced equality invariant, one ordering authority, one provenance owner, and a collision rule; otherwise replay precedence can conceal drift because M349 detail projections overwrite same-id row bindings. Evidence: `2026-07-07-cross-domain-continuity-adr`, Implementation; `src/cadrumo/application/modelo/_revision_replay_inputs.py:99-110`.

The evidence favors Option A for the M347 handoff, but does not settle the cross-modelo carrier policy because M349 editing already depends on typed rows. The ADR must decide whether the carrier is uniform across invoice-derived families or deliberately modelo-specific, and must forbid two silent authorities.

### M349 rectification facts need an authority decision before wiring

One option is an explicit typed rectification-reporting component on `Invoice` containing rectified year, period, previous base, and the semantic meaning of the current base. This supports corrections whose original operation is outside the local catalogue, but duplicates facts if the corrected invoice is locally available and requires official AEAT grounding for correction method and sign semantics.

A second option is to resolve `rectifies_invoice_number` against an immutable prior invoice or filed-revision record and derive the prior year, period, and base. This avoids duplicate entry when evidence is local, but cannot cover a corrected operation absent from the catalogue and must fail closed rather than guess. The current reference is only an invoice number, not a stable catalogue identity or filed-revision coordinate: `src/cadrumo/domain/invoices/models.py:336`.

A third option is to keep automatic invoice-derived M349 rectification unsupported and require `Modelo349RectificacionRow`, while adding a structured refusal or advisory whenever an intracommunity rectificativa would otherwise enter the operador population. This is the safest interim posture and preserves the working manual path, but does not provide automatic materialization. The accepted no-silent-under-declaration contract rules out the current silent default-to-ordinary behavior.

A hybrid can admit local derivation only when the corrected invoice and filing coordinate are provable, otherwise require the explicit typed reporting component or manual row. The ADR must settle precedence when both exist and define mismatches as visible failures, not choose one silently.

### Validation must cross the boundaries current tests isolate

The implementation gate should start with invoices written through the real operator path into the encrypted catalogue, run the enrolled bucket source mesh and calculation persistence, replay the resulting revision, and render the real registry layout. For M347 it must assert multiple counterparties, both invoice directions, both registry revisions, threshold/exclusion behavior, non-resident country projection, stable row ordering, and non-empty persisted row bindings. For M349 it must assert ordinary and rectification records coexist without row collision, cover collectible and payable mirrors, preserve prior year/period and both bases, and render the correct discriminator record.

Negative gates should prove that a rectificativa missing authoritative prior-period/base facts is refused or surfaced as an unresolved filing issue and is never emitted as an operador row; that conflicting manual and derived rows fail under the chosen precedence rule; that absent differs from zero; and that storage degradation remains visible. A detector-teeth fixture should remove the source-resolver row handoff and show the end-to-end gate fails even while the existing domain-resolver and renderer tests remain green. These requirements follow the live handoff locators above and the accepted no-silent-under-declaration and real-authority-path quality rules.

### Scope remains bounded

This research did not determine the legally correct M349 correction method, sign treatment, or whether the prior base may always be derived from a corrected invoice. Those require the exact applicable AEAT record design/instructions and representative official examples before an ADR chooses a data model. It also did not decide row edit identity after automatic regeneration, amendment-versus-recalculation UX, or migration of existing pre-release revisions. No code, registry declaration, or accepted ADR was changed.

## Sources

- `src/cadrumo/application/invoices/source_resolver.py:229-255`
- `src/cadrumo/application/invoices/source_resolver.py:659-689`
- `src/cadrumo/application/invoices/source_resolver.py:914-960`
- `src/cadrumo/domain/invoices/models.py:236-245`
- `src/cadrumo/domain/invoices/models.py:336`
- `src/cadrumo/domain/calculations/registry/invoice_bindings.py:138-141`
- `src/cadrumo/domain/calculations/registry/invoice_bindings.py:694-721`
- `src/cadrumo/application/aggregation/_source_mesh.py:797-813`
- `src/cadrumo/application/modelo/calculation_actions.py:1453-1491`
- `src/cadrumo/application/modelo/_revision_replay_inputs.py:77-116`
- `src/cadrumo/application/modelo/_revision_replay_inputs.py:245-284`
- `src/cadrumo/application/filing/record_renderer.py:162-228`
- `src/cadrumo/application/filing/tests/test_modelo_347_contraparte_export_parity.py:1-32`
- `src/cadrumo/application/modelo/tests/test_revision_replay_inputs.py:267-294`
- `src/cadrumo/_data/registry/aeat/modelos/349/revisions/2020-y-siguientes/export_layouts/0004-record-rectificacion.toml:5-12`
- `2026-08-06-invoice-canonical-structure-adr`, decisions D-C, D-R, D-T
- `2026-08-24-modelo-edit-contract-adr`, decisions D4, D6
- `2026-08-26-tui-architecture-modelo-347-contraparte-binding-inventory-reference`, lines 220-279
- `2026-07-07-cross-domain-continuity-adr`, Implementation
