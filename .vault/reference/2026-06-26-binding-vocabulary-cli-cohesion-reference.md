---
tags:
  - '#reference'
  - '#binding-vocabulary-cli-cohesion'
date: '2026-06-26'
modified: '2026-06-29'
related:
  - "[[2026-06-26-binding-vocabulary-cli-cohesion-adr]]"
  - "[[2026-06-26-bindings-architecture-unification-audit]]"
---

# `binding-vocabulary-cli-cohesion` reference: `phase-2.4 rename and re-home anchors: binding homonyms, CLI verb fork, selector typing`

This reference pins the EXACT rename / re-home sites for phase-2.4 (the final phase of
the bindings-architecture-unification sweep), grounded RAG-first then grep-confirmed
against HEAD (0b5e7926d). Every anchor below was located by a vaultspec-rag code search
for its concept and then confirmed with rg for the precise file:line and current shape.
The phase is a pure rename / re-home (behaviour-preserving); the table is the worklist
the 2.4 plan edits.

Module(s): `aeat.entrypoints.cli`, `aeat.domain.calculations.registry`,
`aeat.application.aggregation`, `aeat.application.calculations`,
`aeat.application.storage.calc_sheets`, `aeat.application.modelo`,
`aeat.application.ledger`, `aeat.domain.iva_compensation`

File(s):
- `src/aeat/entrypoints/cli/_modelo_payloads.py`
- `src/aeat/entrypoints/cli/_modelo_discovery_cli.py`
- `src/aeat/entrypoints/cli/_modelo_work_calculate_cli.py`
- `src/aeat/entrypoints/cli/_config/_google_sync_calc.py`
- `src/aeat/domain/calculations/registry/_queries.py`
- `src/aeat/domain/calculations/registry/_bindings.py`
- `src/aeat/domain/calculations/registry/_schema.py`
- `src/aeat/domain/calculations/registry/_schema_scalars.py`
- `src/aeat/domain/calculations/registry/_schema_surfaces.py`
- `src/aeat/domain/calculations/registry/_m232_row_bindings.py`
- `src/aeat/domain/calculations/registry/_sources.py`
- `src/aeat/application/aggregation/_source_mesh.py`
- `src/aeat/application/aggregation/_service.py`
- `src/aeat/application/calculations/_relation_prefill.py`
- `src/aeat/application/calculations/_binding_prefill.py`
- `src/aeat/application/storage/calc_sheets/_layout.py`
- `src/aeat/application/modelo/_reconcile.py`
- `src/aeat/application/ledger/_business_operation_invoice.py`
- `src/aeat/domain/iva_compensation/_reconciliation.py`

## Summary

### CRITICAL: ADR-vs-HEAD drift (read before scoping the plan)

The ADR Problem Statement and the dispatch brief reference anchor sites that phases
2.1-2.3 already collapsed at HEAD. Three drifts to correct in the 2.4 plan:

1. `_registry_provider.py:102/133` no longer exists. Phase-2.2 (commit `52edec4b1`
   `relocation:PerModeloRegistryBindingResolution`, plus `0d825d774` / `5620ed7f5`
   folding profile+borrador onto one `CalculationSourceResolution`) retired the
   `_registry_provider.py` module entirely. The resolve / provider / resolution tangle
   now lives in `src/aeat/application/aggregation/_source_mesh.py`. Re-point the F6.3
   anchor there (pinned as D1 below). The RAG index still surfaces the dead path because
   it lags HEAD; trust the grep, not the RAG hit, for this one.
2. The canonical resolver contract is settled. `ModeloSourceResolver` (the Protocol port,
   `_source_mesh.py:344`), `CalculationSourceResolution` (the output envelope,
   `_source_mesh.py:200`), and `merge_source_resolutions` (the aggregate) are the
   phase-2.2 outputs F6.3 disambiguates. They are NOT to be renamed; the F6.3 work is to
   rename the OTHER role-family ("provider") that still overloads this settled "resolver"
   concept.
3. `IvaCompensationAuthoritySourceKind` is a `type` alias, not a `StrEnum`. The brief
   implies it is a class like the other two homonyms; at HEAD it is
   `type IvaCompensationAuthoritySourceKind = Literal[...]`
   (`src/aeat/domain/iva_compensation/_reconciliation.py:48`). Treat it as a type-alias
   rename, not a class rename.

All other ADR anchors hold at HEAD.

### Anchor table

| # | Concept | file:line | Current name / shape | Proposed rename / re-home | Consumers / blast-radius | F-finding | 2.4 step |
|---|---------|-----------|----------------------|---------------------------|--------------------------|-----------|----------|
| A1 | CLI bindings-list row payload | _modelo_payloads.py:844 | class BindingRowPayload(OutputSchema) | BindingListRowPayload (CLI list payload) | def + __all__ (:1207) + ModeloBindingsListResult.bindings (:879) + _modelo_discovery_cli.py import (:39) + _binding_list_rows_for_report (:422,428,433,492) + test docstring test_modelo_registry_surface.py:882. ~8 sites | F6 (BindingRow 1/4) | S(BindingRow rename) |
| A2 | CLI bindings-preview row payload | _modelo_payloads.py:882 | class BindingPreviewRowPayload(OutputSchema) | keep (already role-distinct; only bare BindingRow stem of A1 collides) | def + __all__ (:1206) + ModeloBindingsPreviewResult.bindings (:911) + _modelo_discovery_cli.py import (:38) + builder (:594). ~5 sites; likely no-op | F6 (BindingRow 2/4) | S(BindingRow rename) |
| A3 | registry-query binding row | registry/_queries.py:243 | class ModeloBindingRow(BaseModel) | ModeloBindingQueryRow (registry-query projection) | def + tuple field (:328) + builder _binding_rows (:937,947) + __all__ (:989) + registry pkg __init__.py re-export (:241,490) + _schema.py:1016 docstring xref. ~7 sites incl. docstring-core-struct graph | F6 (BindingRow 3/4) | S(BindingRow rename) |
| A4 | calc-sheets layout binding row | calc_sheets/_layout.py:77 | class _BindingRow(BaseModel) (module-private) | _EntradasBindingRow (calc-sheets ENTRADAS-tab layout row) | def + 5 uses in same module (:126,412,434,441,452). Module-private; blast radius is one file | F6 (BindingRow 4/4) | S(BindingRow rename) |
| B1 | M232 row materialiser (false-friend IN registry binding pkg) | registry/_m232_row_bindings.py:1,31 | file _m232_row_bindings.py; fn materialize_m232_related_party_rows returns tuple[CasillaObservation,...] -- a CLI-row materialiser, NOT a DataBindingDefinition family | re-home OUT of registry binding pkg; rename file to drop _bindings (e.g. _m232_row_materialisation.py) toward domain/modelos row-model surface | only consumer is src/aeat/tests/test_storage_decimal_redaction_error_typing.py:347 (direct submodule import). NOT in registry __all__. ~2 sites | F6 (false-friend 1/2) | S(re-home false-friends) |
| B2 | BOE corpus verifier (false-friend IN registry binding pkg) | registry/_sources.py:1,14 | file _sources.py; verify_source_file / verify_source_catalogue -- a BOE corpus-catalogue integrity verifier, unrelated to binding source KINDS | rename file to say corpus-catalogue (e.g. _corpus_catalogue.py); source here = a SourceReference corpus file, not BindingSourceKind | _validate.py:22, registry __init__.py re-export (:356,734), 3 test modules (test_catalogue_verification.py, test_censo_modelo_registry_data.py, test_modelo_145_source_catalogue.py). ~10+ sites incl. pkg __all__ | F6 (false-friend 2/2) | S(re-home false-friends) |
| C1 | reconcile-transport source kind | application/modelo/_reconcile.py:35 | class ModeloReconciliationSourceKind(StrEnum) {JUSTIFICANTE, DECLARATION} | ModeloReconciliationEvidenceKind (reconcile transport / external-evidence kind) -- distinct axis, NOT folded into BindingSourceKind | 30 occurrences across 6 files: _modelo_reconcile_cli.py, application/modelo/__init__.py (re-export), _reconcile.py, _justificante.py, 2 test modules | F6 (SourceKind homonym 1/3) | S(reconcile SourceKind homonyms) |
| C2 | invoice-direction source kind | application/ledger/_business_operation_invoice.py:53 | class BusinessOperationInvoiceSourceKind(StrEnum) {PAYABLE_INVOICE, COLLECTIBLE_INVOICE} | rename TYPE to BusinessOperationInvoiceDirection. NOTE: internal payable_invoice/collectible_invoice taxonomy load-bearing per aeat-spanish-stem-naming; rename ENUM TYPE, KEEP member string values | 31 occurrences across 6 files: _ledger_business_invoice_cli.py, invoices/_source_resolver.py, _business_operation_invoice.py, ledger/__init__.py (re-export), 2 test modules | F6 (SourceKind homonym 2/3) | S(reconcile SourceKind homonyms) |
| C3 | wallet-authority source kind | domain/iva_compensation/_reconciliation.py:48 | type IvaCompensationAuthoritySourceKind = Literal[...] (TYPE ALIAS, not a class) | IvaCompensationAuthorityKind (wallet/compensation authority) -- distinct axis | 5 occurrences across 2 files: _reconciliation.py (def :48, fields :84,550, __all__ :598) + docs/conf.py:547 nitpicky-resolver allowlist. The binding usages in this module (:104,108,180,545,556) are the legitimate M303 compensacion carve-out binding; do NOT re-home | F6 (SourceKind homonym 3/3) | S(reconcile SourceKind homonyms) |
| D1 | resolve/provider/resolution tangle (re-pointed from dead _registry_provider.py) | _source_mesh.py:344 (port), :200 (output), merge_source_resolutions (aggregate) | ModeloSourceResolver (port), CalculationSourceResolution (output) -- SETTLED by 2.2, do NOT rename | OVERLOAD to fix is the OTHER role-family still called provider: PerModeloAggregationProvider / PerModeloAggregationProviderContract (_service.py:47,73), RegistrySchemaProvider/CasillaSchemaProvider (application/filing/runtime.py:192). Disambiguate name to say PORT vs OUTPUT vs AGGREGATE vs provider role-family | _service.py provider enum/contract (~12 sites), filing/runtime.py schema-provider (~6 sites). Resolver contract widely consumed but NOT renamed | F6 (resolve/provider tangle) | S(resolve/provider tangle) |
| E1 | Observation family -- calc canonical anchor | registry/_bindings.py:202,276,335 | CasillaObservation, RegistryModeloObservation, OracleModeloObservation | the calc/casilla tier the prefix discipline organises AROUND (not a rename target); flag the 30+ cross-domain *Observation carriers lacking a domain prefix (see E2) | CasillaObservation is the primary storage of RegistryCalculationResult -- very wide; anchor only | F6 (Observation family) | S(Observation prefix discipline) |
| E2 | Observation family -- undiscriminated cross-domain carriers | enumerated below | 30+ *Observation data carriers across unrelated tiers | give domain-discriminating prefixes where the bare Observation stem collides across tiers (calc / ledger-aggregation / live-capture / oracle) | see the Observation-family enumeration section | F6 (Observation family) | S(Observation prefix discipline) |
| F1 | prefill 1 -- relation | application/calculations/_relation_prefill.py:1 | Relation prefill module; RelationPrefillSourceResolver (:610) | keep relation prefill (relation tier) -- assert distinction from F2/F3, do not merge | wide (relation enrollment path); naming-clarity only | F6 (prefill x3) | S(prefill disambiguation) |
| F2 | prefill 2 -- previous-filing carry | application/calculations/_binding_prefill.py:1 | Binding prefill module (resolves previous_filing bindings); sister to _relation_prefill | keep binding prefill (previous_filing direct-carry tier) | distinct from F1; same-modelo direct carry | F6 (prefill x3) | S(prefill disambiguation) |
| F3 | prefill 3 -- AEAT borrador pre-fill | registry/_schema.py:1026 (aeat_prefilled), :1009 borrador-fed typed_enum | aeat_prefilled: bool -- the AEAT borrador pre-filled-return concept | keep aeat_prefilled (AEAT-live tier) -- distinct from local prefill tiers F1/F2 | borrador binding resolver, Sheets-pull router | F6 (prefill x3) | S(prefill disambiguation) |
| G1 | CLI verb fork -- bindings preview | _modelo_discovery_cli.py:530 | bindings_app.command preview under app modelo bindings subgroup (:75,81,86) | one learnable verb story per aeat-cli-pull-and-file-standard; preview names a UI gesture, not the value-bearing aggregation it performs | locale keys cli.app.modelo.bindings.preview_help + list_help; bindings_app registration | F7 (CLI verb fork 1/3) | S(CLI verb reconciliation) |
| G2 | CLI verb fork -- calc pull --compute | _config/_google_sync_calc.py:361 | calc_app.command pull + --compute/--no-compute (:373-376) under config google sync calc | reconcile with G1/G3 -- same produce-bound-casilla-values-from-sources intent; pull here multiplexes Sheets transport + compute | locale keys cli.config.google.sync.calc.pull*; the pull channel multiplexing | F7 (CLI verb fork 2/3) | S(CLI verb reconciliation) |
| G3 | CLI verb fork -- work calculate | _modelo_work_calculate_cli.py:253 | work_app.command calculate under app modelo work | the live calculate path -- the canonical aggregation engine entry | locale key cli.app.modelo.work.calculate_help; register_work_calculate_commands | F7 (CLI verb fork 3/3) | S(CLI verb reconciliation) |
| H1 | binding selector (hydrated source-family model) | registry/_schema.py:839; alias _schema_scalars.py:399 | DataBindingDefinition.selector: BindingSelector; raw BindingSelectorMap is authoring/input shape only | closed/currentized 2026-06-29: the constructed binding schema hydrates raw TOML/dict selectors through selector_model_for_source into concrete per-family pydantic selector models, serializes them back to authored mappings, and refuses mesh-only borrador / iva_wallet_decision as registry binding sources. Binding-derived export record projection parses through BindingFixedExportSelector / BindingRowExportSelector, Detalle row-set assembly and Sheets layout parse through BindingRowSetSelector, and public binding query rows expose BindingSelectorQueryProjection ordered entries instead of the raw selector map. | _schema.py selector field + serializer; _schema_scalars.py BindingSelector; per-source typed selector models in _bindings.py; _validate_binding_selector_shapes snapshot gate; ModeloBindingQueryRow.selector projection BindingSelectorQueryProjection | F8 (selector typing) | closed for H1 |
| H2 | typed_enum closed enum-class annotation | registry/_schema.py:841; core/aggregation.py:353 | DataBindingDefinition.typed_enum: BindingTypedEnumKind \| None; raw TOML tokens hydrate at the schema boundary | closed/currentized 2026-06-29: the canonical binding schema stores a closed enum member instead of a bare string pointer. `ModeloBindingQueryRow.typed_enum` remains string-valued as an operator/API projection because StrEnum serializes to its token. | bindings list CLI table, ModeloBindingQueryRow (A3) projection, borrador resolver, Sheets-pull router; gated by `test_schema_hygiene.py::test_declared_typed_enum_hydrates_to_binding_typed_enum_kind` | F8 (selector typing) | closed |
| H3 | DISTINGUISH: relation source-revision selector | _schema_surfaces.py:483 | source_revision_selector: Mapping[str, str-or-int] on the relation/dependency surface | NOT the binding selector (H1) -- this is the RELATION revision selector. Do not conflate; F8 touches H1, not H3 | _relations.py:281, _validate_relation_sources.py:88,122,123,159, cross-dependency tests | F8 (disambiguation note) | n/a (clarifier) |

### Observation-family enumeration (E2 detail)

The bare *Observation stem spans 30+ types across unrelated tiers. Grouped by the
discriminating prefix discipline the phase should apply:

- Calc / registry tier (canonical): CasillaObservation (registry/_bindings.py:202),
  RegistryModeloObservation (:276), OracleModeloObservation (:335), ObservationPayload
  (cli/_modelo_payloads.py:67), CasillaObservationPayload (:1030),
  ModeloProjectionCasillaObservation (application/modelo/_projection.py:139),
  EnrollmentYearObservation (application/calculations/_multi_year.py:91). These already
  read as calc/casilla; the anchor the others organise around.
- Ledger-aggregation tier (needs a consistent prefix): IvaLedgerObservation,
  OssIossLedgerObservation (registry/_ledger_bindings.py:299,86), RetencionObservation
  (aggregation/_retenciones.py:32), CounterpartObservation (aggregation/_counterpart.py:46),
  CounterpartAggregationObservation (registry/_counterpart_bindings.py:47),
  ForeignAssetIngestObservation (aggregation/_foreign_assets.py:50),
  RentaDeductibleExpenseObservation (renta/_ledger_expenses.py:185), the detail-record
  family (RelatedPartyOperationObservation, Modelo720RowObservation,
  AtributionMemberObservation, RefundOperationObservation in
  registry/_detail_record_bindings.py:79,216,350,472), WithholdingObservation
  (registry/_withholding_bindings.py:57), InvoiceObservation
  (registry/_invoice_bindings.py:68).
- Live-capture / sede tier: FiledDeclaracionObservation
  (adapters/outbound/aeat/sede/_schema.py:247), IvaCompensationWalletObservation (:223),
  NifIvaCheckObservation (sede/_nif_iva_check.py:137), DeclaracionObservation
  (adapters/inbound/declaracion/_schema.py:77), BorradorObservation
  (adapters/inbound/borrador/_schema.py:69).
- Oracle tier: RentaWebOpenObservation (registry/_renta_web_open_oracle.py:96),
  GroiObservation (registry/_groi_oracle.py:71), AeatNifIvaObservation
  (registry/_aeat_nif_iva_oracle.py:52), plus OracleModeloObservation (calc tier,
  oracle-marked).

The *ObservationRequirement / *ObservationProtocol / *ObservationRepository /
*ObservationStore suffixes (e.g. WithholdingObservationRequirement,
CalculationObservationRepository, FiledDeclaracionObservationStore) are role-suffixed and
read clearly; they are NOT the homonym problem and need no rename -- only the bare
*Observation data carriers across tiers do.

### Rename blast-radius estimate per F-finding (for 2.4 plan scoping)

- F6 *BindingRow (A1-A4): ~22 sites across 4 files plus the docstring-core-struct graph
  (A3 is a CORE_STRUCTS-adjacent xref). Small, mechanical, atomic per type. A2/A4 may be
  no-ops (already role-distinct / module-private). Real renames: A1, A3.
- F6 false-friends (B1-B2): B1 ~2 sites (re-home + one test import); B2 ~10+ sites incl.
  the registry __all__ re-export -- larger because verify_source_* is a public registry
  surface with three test consumers. Both are file relocations: trigger
  dev.docs.apidocs scaffold (API-stub regen) in the same atomic commit.
- F6 genuine *SourceKind homonyms (C1-C3): C1 ~30 sites, C2 ~31 sites, C3 ~5 sites. C1/C2
  are the wide ones (CLI + re-export + tests each). C2 must preserve member STRING values
  (payable_invoice/collectible_invoice are load-bearing). C3 also touches the
  docs/conf.py nitpicky-resolver allowlist.
- F6 resolve/provider tangle (D1): the resolver contract is NOT renamed (settled by 2.2);
  the rename targets the provider role-family -- PerModeloAggregationProvider (~12 sites)
  plus the schema-provider family (~6 sites). Medium.
- F6 prefill (F1-F3) + Observation prefix (E1-E2): prefill is a naming-clarity pass (the
  three modules already carry distinct names; the work is asserting the distinction --
  low blast radius). Observation prefixing is the WIDEST F6 item if pursued fully (30+
  carriers, many with wide consumers); recommend scoping to the cross-tier collisions
  only, or deferring per-tier passes.
- F7 CLI verb fork (G1-G3): the rename is operator-visible and locale-bound. Each verb
  rename sweeps the Typer registration, the locale catalogue (via python -m aeat.locales
  modelo / set), the runtime write-policy allowlist (storage_write_policy.py), the
  error-registry default_suggestion fields, the cross-period next_action builders, the
  curated operator help (operator_surface/_help.py), and the envelope command= identifiers
  -- per aeat-cli-pull-and-file-standard. HIGH blast radius; the registration is the small
  part. Gated by test_documented_command_conformance.py and test_json_schema_conformance.py.
- F8 selector typing (H1-H2): H1 and H2 are closed in current state. Binding
  selectors hydrate to per-source models, and `typed_enum` hydrates to
  `BindingTypedEnumKind`; public query rows still serialize enum annotations as
  string tokens.

### What is NOT in scope (guardrails)

- ModeloSourceResolver, CalculationSourceResolution, merge_source_resolutions (phase-2.2
  settled -- renaming them re-churns a just-landed phase).
- BindingSourceKind itself (phase-2.1 authority) -- the three C-homonyms are reconciled as
  DISTINCT axes, never folded in.
- The iva_compensation binding usages (_reconciliation.py:104,108,180,545,556) -- the
  legitimate M303 compensacion carve-out registry-input binding, correct per
  binding-names-reserved-for-registry-input.
- The *ObservationRequirement / *Repository / *Store / *Protocol role-suffixed names --
  already clear.
