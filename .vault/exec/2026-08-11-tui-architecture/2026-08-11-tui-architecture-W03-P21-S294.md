---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-27'
modified: '2026-08-27'
body_schema: 'body-v2'
body_hash: 'sha256:550158727e00d09a49c02dae41e73ff415e33b3d3e2022cc95cb74187a1e6f2e'
step_id: 'S294'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Stop the modelo 347 contraparte record truncating a multi-counterparty declaration to a single counterparty, which needs a per-row binding family built rather than rewired: its export record carries manual scalar casilla fields with no repeat marker, and unlike modelo 184 no resolver produces row-indexed contraparte values at all, the row type being consumed only by threshold validation; build the per-row binding family and resolver on the pattern the 349 operador rows already establish, wire the export record onto it, and prove a real multi-counterparty declaration emits one occurrence per counterparty

## Scope

- `the modelo 347 contraparte bindings and export record`
- `a new per-row contraparte resolver enrolled in the calculate mesh`
- `and a real multi-counterparty M347 export parity test`

## Changes

- `A` `src/cadrumo/_data/registry/aeat/legal/operaciones-terceros.toml` -- grounded RD 1065/2007 arts. 33 and 34
- `A` `src/cadrumo/_data/registry/aeat/modelos/347/revisions/2025-y-siguientes/bindings/0002-contraparte-clave.toml`
- `M` `src/cadrumo/domain/calculations/registry/invoice_bindings.py` -- `operation_clave` field, `m347_operation_clave`, `contraparte_clave` grouping, `_build_contraparte_clave_rows`, grouping-scoped cohort/observation-source union
- `M` `src/cadrumo/domain/calculations/registry/binding_selector_utils.py` -- parameterized `operation_clave_validator`, `M347_OPERATION_CLAVES`/`M349_OPERATION_CLAVES`
- `M` `src/cadrumo/domain/modelos/_row_models.py` -- narrowed `_M347_CLAVE_OPERACION` to `Literal["A".."G"]`
- `A` `src/cadrumo/domain/calculations/registry/tests/test_m347_operation_clave.py`
- `A` `src/cadrumo/domain/calculations/registry/tests/test_contraparte_clave_row_grouping.py`
- `A` `src/cadrumo/domain/calculations/registry/tests/test_m349_rows_unaffected_by_contraparte_clave_extension.py`
- `A` `src/cadrumo/domain/calculations/registry/tests/test_modelo_347_contraparte_clave_bindings.py`
- `M` `src/cadrumo/core/corpus_text.py` -- resolves an anchor verbatim before canonicalising (fixes a pre-existing 114-collision corpus-wide defect this Step's grounding surfaced)
- `M` `src/cadrumo/core/aggregation.py` -- new `BindingSourceKind.M347_THIRD_PARTY_OPERATION`, grounded on RD 1065/2007 art. 33.1; added to `INVOICE_BINDING_SOURCE_KINDS`
- `M` `src/cadrumo/application/aggregation/_source_mesh.py` -- new member added to the `deterministic_lock` precedence tier
- `M` `src/cadrumo/application/invoices/_source_resolver.py` -- new member added to `_OWNED_SOURCES`
- `M` `src/cadrumo/domain/calculations/registry/bindings.py` -- new member registered in both selector-model and validator dispatch tables
- `M` `src/cadrumo/application/modelo/_data_inventory.py` -- new member added to `_LIVE_OBSERVATION_SOURCE_KINDS`
- `M` `src/cadrumo/application/state_projection.py` -- new member added to the readiness locale-key and operator-action projections (new locale key `cli.app.modelo.bindings.readiness.operacion_tercero`)
- `M` `src/cadrumo/_data/registry/aeat/modelos/347/revisions/2011-2024/bindings/0001-counterpart-summary.toml` -- retargeted `source` to `m347_third_party_operation`
- `M` `src/cadrumo/_data/registry/aeat/modelos/347/revisions/2025-y-siguientes/bindings/0001-counterpart-summary.toml` -- retargeted `source`
- `M` `src/cadrumo/_data/registry/aeat/modelos/347/revisions/2025-y-siguientes/bindings/0002-contraparte-clave.toml` -- retargeted `source`
- `M` locale catalogues (es/en/ca/hu): `docs.casilla.binding_source.m347_third_party_operation`, `flows.modelo_review.filter.option.binding_source.m347_third_party_operation`, `cli.app.modelo.bindings.readiness.operacion_tercero`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_binding_source_kind_taxonomy.py`, `test_invoice_measure_classification.py`, `test_modelo_347_registry_bindings.py`, `src/cadrumo/application/aggregation/tests/test_precedence_ladder_conformance.py`, `src/cadrumo/application/invoices/tests/test_source_resolver.py` -- updated to the honest source declaration
- `M` `src/cadrumo/domain/calculations/registry/invoice_bindings.py` -- `_m347_quarter_of`, `_M347_QUARTER_ROW_FIELDS`, quarterly bucketing in `_build_contraparte_clave_rows` (calendar quarter of `transaction_date` via `Period.contains`, annual total is the sum of the four by construction); removed the now-redundant `shares_one_sequence_across_sources` cohort special-case
- `M` `src/cadrumo/_data/registry/aeat/modelos/347/revisions/2025-y-siguientes/bindings/0002-contraparte-clave.toml` -- four new `importe-q{1..4}` row bindings, grounded `rd-1065-2007:art-33`
- `M` `src/cadrumo/_data/registry/aeat/modelos/347/revisions/2025-y-siguientes/export/0002-record-m347-declarado.toml` -- **the export repoint**: `repeat = 'binding_rows'`, `row_field_casilla_ids`, nif/nombre/clave/importe-anual/importe-Q1..Q4 converted to `kind = 'binding'`; every diseño-conditional field (importe-metalico, transmisiones-inmuebles pair, operacion-seguro, arrendamiento-local-negocio, criterio-caja, etc.) stays scalar/unbound by design
- `A` `src/cadrumo/application/filing/tests/test_modelo_347_contraparte_export_parity.py` -- the multi-counterparty export parity proof: two/three-counterparty row resolution, renderer-level row emission, quarters summing exactly to the annual total for a real invoice in each quarter, a quarter-boundary date (Mar 31/Apr 1), and conditional fields confirmed off the binding path
- `verify:` `uv run --no-sync python -c "from cadrumo.domain.calculations.registry.authority import bundled_authority; bundled_authority()"` -> `pass` (registry loads clean)
- `verify:` `uv run --no-sync pytest src/cadrumo/application/filing/tests/test_modelo_347_contraparte_export_parity.py src/cadrumo/domain/calculations/registry/tests -q -m unit -k "347 or invoice or binding_selector or counterpart or clave or contraparte or m349 or legal_grounding or source_kind or taxonomy"` -> `pass` (256 passed)
- `verify:` `grep -rn 'm347_third_party_operation' src/cadrumo/_data/registry` -> 8 bindings declare it (all six the finding named, plus the two pre-existing 2011-2024 declarante-summary bindings retargeted in the same sweep)

## Notes

**Step is now substantively complete for the `2025-y-siguientes` revision**:
the per-row binding family, the source-declaration honesty fix, the mandatory
quarterly desagregación, and the export repoint (with its multi-counterparty
parity proof) are all built and tested against the real bundled revision. The
truncation the Step's own title names is stopped for claves A/B on that
revision. Remaining scope, all explicitly deferred below, keeps the Step from
being marked fully done at the Epic's original breadth.

Explicitly deferred, stated rather than silently dropped:
- Claves C-G: each needs a fact `m347_operation_clave` cannot classify from
  `source_kind` alone (filer type, cobro-por-cuenta-de-terceros nature, or a
  mediación-de-agencia-de-viajes flag under RD 1619/2012, per the CLAVE
  classification table in the reference doc).
- The quarterly transmisiones representation gap (its own audit document,
  `2026-08-26-tui-architecture-modelo-347-contraparte-quarterly-transmisiones-representation-gap-audit`),
  now grounded against RD 1065/2007 art. 34.1.i) but not resolved -- distinct
  from the ordinary Q1-Q4 desagregación this Step DID build.
- The 2011-2024 revision (needs the same row-binding-family and export-repoint
  buildout; only its declarant-summary placeholder and the source-declaration
  fix landed there so far).
- Every other conditional field on the declarado record left scalar by
  design (importe-metalico, operacion-seguro, arrendamiento-local-negocio,
  criterio-caja/importe-criterio-caja, inversion-sujeto-pasivo,
  bienes-vinculados, numero-convocatoria-bdns, nif-operador-comunitario,
  representante-legal-nif, pais-codigo) -- each gated by its own "Sólo..."/
  exception clause in the diseño text, per the conditional/mandatory
  discrimination method recorded below, except `representante-legal-nif` and
  `pais-codigo`, which are per-counterparty IDENTITY facts (not money) with
  no per-row source yet; flagged here as a real but smaller, non-money gap
  outside this Step's money-bearing scope, not resolved.
- ~~A source-declaration auditability gap...~~ RESOLVED: both the
  pre-existing declarante-summary bindings (both revisions) and the new
  contraparte-clave bindings now declare the honest combined-direction
  `BindingSourceKind.M347_THIRD_PARTY_OPERATION`, grounded in RD 1065/2007
  art. 33.1's undifferentiated "operaciones" concept. Two-bindings-per-field
  was investigated and found non-viable: each casilla binds to exactly one
  `BindingId` in the export layout, so a competing pair would need either an
  arbitrary export-layer pick or a merge concept the registry does not have.
  Enrolled through every consumer surface a grep found: the LOCK precedence
  tier, `_OWNED_SOURCES`, both bindings-dispatch tables, the data-inventory
  live-observation classification, and the readiness locale-key/operator-
  action projections (new locale key, all four languages). A grep for the
  new source kind now finds every one of the six named bindings (plus the
  two 2011-2024 bindings retargeted in the same sweep) -- the auditability
  property the change exists for.

Structural grounding for the cohort/union fix, restated per instruction: the
diseño de registro's only sequence split is REGISTRO DE DECLARADO versus
REGISTRO DE INMUEBLE -- two different record layouts sharing the type-2
marker, disambiguated by their own discriminator field. CLAVE OPERACIÓN at
position 82 is a single-value field WITHIN one declarado record, not a
record-type discriminator, so a counterparty with both an adquisición and an
entrega necessarily emits TWO declarado records (one per clave, since one
record cannot carry two clave values), and both are the SAME record type in
the SAME physical stream. There is no warrant in the diseño for two
independent row-index sequences by invoice direction; RD 1065/2007 art.
33.1's "se computarán de forma separada las entregas y las adquisiciones"
governs separate THRESHOLD ACCOUNTING per direction, a different axis from
the physical record stream.

M349 invisibility proven directly, not assumed: `test_m349_rows_unaffected_
by_contraparte_clave_extension.py` pins the exact row output of the real,
unmodified `2020-y-siguientes` operador-adquisicion bindings and a refusal
case through the production `validate_invoice_binding_definition` entry
point, both before and after the cohort-key and observation-source changes.

Conditional-versus-mandatory field discrimination method, named because it
generalises to any repeating-record repoint: classify by whether the DISEÑO
ITSELF gates the field with an explicit "Sólo..."/exception clause, never by
whether test data happens to populate it. `importe-metalico` gates on cash
>6.000 EUR, `operacion-seguro` on Entidades Aseguradoras only,
`arrendamiento-local-negocio` on that specific lessor/lessee population, the
transmisiones-inmuebles pair on real-estate operations only -- each
blank-when-inapplicable by the document's own words. `importe-Q1..Q4` carries
no such gate ("el importe de las operaciones realizadas en el [Nth]
trimestre, con cada persona" is unconditional for every reported operation),
so it was mandatory and had to be built before `repeat` could be declared.

Quarterly bucketing is built as a calendar-quarter split of the SAME
`invoice_total_amount` `_build_contraparte_clave_rows` already sums,
accumulated in the same loop so the annual total is the sum of the four
quarters by construction rather than a separate reconciling step, and keyed
through `Period.from_year_and_code(transaction_date.year, token).contains(...)`
-- the one canonical period-boundary authority
(`aeat-registry-authority-flow`'s period-boundary rule) -- rather than
re-derived month-range arithmetic. Proven with a real invoice in every
quarter (quarters sum exactly to the annual total) and one on the Q1/Q2
boundary date (Mar 31 correctly separate from Apr 1).

A pre-existing, corpus-wide defect was found and fixed along the way (not
this Step's own scope, landed by a peer once reported): 21 hyphenated
anchors in the RD 1065/2007 sidecar and 114 colliding anchor keys across 12
bundled sidecars could not be cited at all, because anchor canonicalisation
stripped hyphens and collided distinct articles (e.g. `#a3-3` and `#a33`).
Found while grounding arts. 33/34; reported rather than worked around;
fixed in `core/corpus_text.py` by trying a verbatim anchor match before the
canonical one.
