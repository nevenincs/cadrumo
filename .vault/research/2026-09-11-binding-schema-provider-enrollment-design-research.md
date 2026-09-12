---
tags:
  - '#research'
  - '#binding-schema'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:67f5e78b62126bd04716c6cd877004ab314e658515116ef91a743a3020a3c7ed'
related:
  - "[[2026-09-11-binding-schema-research]]"
  - "[[2026-09-09-registry-edition-authoring-adr]]"
---

# `binding-schema` research: `provider enrollment and closed binding schema design`

The question is what a revision-local binding declaration must contain so that its semantic identity closes, through enrolled code, to a typed terminal value origin. The evidence picture: the corpus location and hydration are enrolled, but the binding "union" is three parallel dispatch tables plus a dozen resolvers that re-read selector fields, seven authored source kinds have no runtime owner and escape the novel-source refusal through the row exemption, relation-prefill bindings restate the relation's source descriptor without a typed reference, and the filing-year delta grammar exists in three places. The edition-authoring decision has since fixed binding inheritance by identifier with retirements in a sibling `binding_evolutions` section, which removes the per-binding lineage axis from this schema. The evidence favors a hard cut to `BindingDefinition(provider=BindingProvider)` with one `BindingProviderRegistration` authority from which selector, validator, and route lookups derive; the ADR must still settle the relations boundary, the terminal-origin vocabulary, and the value-channel set. This document extends the earlier binding-schema research and does not restate what it already establishes about loader shape and the facts precedent.

## Findings

### Current registry shape: the fragment loader is generic, the inline-binding refusal is fragment-mode only

Section directories are discovered generically (every subdirectory except `locales/`) and section fields are derived from `ModeloRevision.model_fields`, so `bindings/` is a section by derivation, not by name. `dev/registry/compiler/_loader_internals.py:1137`; `dev/registry/compiler/loader_grammar.py:17-34`. The refusal of inline `bindings` in `revision.toml` lives only in the directory branch. `dev/registry/compiler/_loader_revision_fragments.py:107-115`. The flat `revisions/*.toml` and single-file modelo branches still pass inline bindings through untouched. `dev/registry/compiler/_loader_internals.py:1104`; `dev/registry/compiler/loader.py:60`. The corpus uses neither branch, so these are removable under the no-legacy-compatibility policy, not a migration concern.

Publication serializes each binding's selector by `model_dump` of the hydrated model with `exclude={"source"}`, so `authority.json` carries the authored mapping without a tag. `src/cadrumo/domain/calculations/registry/schema.py:350`; `src/cadrumo/domain/calculations/registry/authority_artifact.py:407`. Runtime re-hydrates through the same before-validator, so the artifact is readable only because the sibling `source` field survives beside it.

Edition inheritance now extends to bindings: a successor edition declares only new or differing bindings, identity is the edition-free identifier, and withdrawal is an authored `retired` or `replaced` row in `binding_evolutions/*.toml`. `.vault/adr/2026-09-09-registry-edition-authoring-adr.md:92-135`. The materialiser merges casillas only today; binding merge by identifier is scheduled after the casilla migration. The schema below is designed against the inherited shape.

### Partial-migration diagnosis: hydration landed, the closed type did not, and three docstrings claim otherwise

The stored annotation is `BindingSelector = SerializeAsAny[BaseModel]`, the field admits `BindingSelector | Mapping[str, object]`, and two hand-written passes (`_coerce_selector` before construction, `_validate_selector_shape` after) do the work a discriminator would do once. `src/cadrumo/domain/calculations/registry/schema_scalars.py:515`; `src/cadrumo/domain/calculations/registry/schema.py:266,320-348,386-435`. No `Field(discriminator=...)` exists in the registry package outside governed facts. `src/cadrumo/domain/calculations/registry/facts/schema.py:376-384`; `src/cadrumo/domain/calculations/registry/facts/resolution.py:121,216`.

Three in-code comments describe the lookup dict as a "discriminated-union selector table", and the vocabulary plan checked step `W05.P08.S25` whose own text marks it deferred. `src/cadrumo/domain/calculations/registry/schema.py:392-395`; `src/cadrumo/domain/calculations/registry/bindings.py:889-895,950-951`; `.vault/plan/2026-06-26-binding-vocabulary-cli-cohesion-plan.md:107-117`. The TUI reference presupposes a union branch that does not exist. `.vault/reference/2026-08-25-tui-architecture-s127-workspace-field-manifest-reference.md:54`. These are documentation debts to clear in the same change as the cut.

The downstream cost of the open type is visible: the query projection re-flattens selectors into `str | int | bool | tuple[str, ...]` entries and re-derives a public selector from a string source. `src/cadrumo/domain/calculations/registry/query_reports.py:201-220`; `src/cadrumo/domain/calculations/registry/queries.py:966-1010`.

### Consumer and casilla-binding taxonomy: four validated reference surfaces, one accessor, four ad-hoc re-splats

Typed consumers of a binding id and the compiler check that resolves each:

| Consumer | Field | Compiler resolution |
| --- | --- | --- |
| Casilla primary | `CasillaDefinition.binding` `src/cadrumo/domain/calculations/registry/schema_surfaces.py:378` | `dev/registry/compiler/_validate_record_sections.py:124-128` |
| Casilla alternates | `alternate_bindings` `schema_surfaces.py:379-387` | same |
| Formula operand | `binding`, `date_binding` `src/cadrumo/domain/calculations/registry/schema_formula.py:150-151,175-176` | `dev/registry/compiler/validate_formulas.py:121-122` |
| Export field | `binding` `src/cadrumo/domain/calculations/registry/schema_exports.py:464` | `dev/registry/compiler/validate_exports.py:435-436` |
| Repeated export rows | `BINDING_ROWS`, `binding_record` `schema_exports.py:111,830-884` | `validate_exports.py:393` |
| Relation target | `RelationDefinition.target_binding` `schema_surfaces.py:901` | `dev/registry/compiler/_validate_dependency_sections.py:70-71` |
| Detail-record projection | `dict[tuple[BindingId, int], ...]` `src/cadrumo/domain/calculations/registry/detail_record_bindings.py:324,342,526,567` | via owning family validator |
| Application query | `query_reports.py:155,228,263` | none (projection) |

Casilla `input_kind` invariants: COMPUTED must not declare a binding, non-BOUND must not declare alternates, BOUND must declare a primary, primary must not repeat in alternates. `schema_surfaces.py:283-343,481-490`. Alternate agreement is enforced at runtime by exact `Decimal` inequality with first-wins ordering and no source-family or data-type check on alternates. `src/cadrumo/domain/calculations/registry/bindings.py:425-450`. That is the correct conflict semantics (reviewed equivalents, not fallback), but the schema does not yet require alternates to share a value contract with the primary; the proposed `value` block makes that checkable.

The canonical accessor `bound_casilla_binding_ids` / `casillas_by_binding` is bypassed in four places that re-splat `(binding, *alternate_bindings)`. `src/cadrumo/domain/calculations/registry/binding_targets.py:22,31`; `src/cadrumo/application/aggregation/modelo_bindings.py:1048`; `src/cadrumo/application/aggregation/iva_ledger.py:1350`; `dev/docs/casilla_reference.py:606`; `dev/registry/compiler/_validate_export_exemption.py:161`. A compiler-derived reverse consumer index would make these unnecessary and would give the "binding referenced by no typed consumer" gate a single source.

### Provider and source taxonomy: 30 authored kinds, 2 mesh-only, 2 pseudo-owned, 7 unowned

`BindingSourceKind` has 32 members; `BORRADOR` and `IVA_WALLET_DECISION` are mesh-only and refused at construction because they have no selector model. `src/cadrumo/core/aggregation.py:348-358`; `src/cadrumo/domain/calculations/registry/bindings.py:906-965`; `src/cadrumo/domain/calculations/registry/schema.py:333-338`. `MANUAL_INPUT` and `DESIGN_CONSTANT` are pseudo-owners with no resolver. `src/cadrumo/application/modelo/calculation_route.py:132-141`.

Authored corpus (all `bindings/*.toml`): 9235 `source =` rows, 4312 distinct ids. The 2x ratio is edition restatement, which the inheritance decision eliminates. Manual input dominates (8012 rows), then ledger IVA (499), withholding (203), profile (128), relation prefill (105). No source kind is unauthored except the three noted as zero in the matrix.

Output channel per resolver: five resolvers produce rows (`detail_rows` or `row_binding_values`): invoice catalogue, foreign assets, atribucion member, inventory, IRNR income. `src/cadrumo/application/invoices/source_resolver.py:248`; `src/cadrumo/application/aggregation/foreign_assets.py:364,488`; `src/cadrumo/application/aggregation/atribucion_member.py:116-117`; `src/cadrumo/application/aggregation/inventory.py:206`; `src/cadrumo/application/aggregation/modelo_bindings.py:809`. All others are scalar. The row/scalar split is load-bearing: the novel-source refusal exempts `aggregation.op == ROWS`. `src/cadrumo/application/modelo/calculation_actions.py:1781-1792`.

### Enrollment completeness matrix

Authored rows from the corpus count; provider model from `_BINDING_SELECTOR_REGISTRY`; validator from `_BINDING_VALIDATOR_REGISTRY` (`selector-only` means `_validate_selector_only`, `family` means a dedicated validator); runtime owner from `_CANONICAL_RESOLVER_STAGES` `src/cadrumo/application/modelo/calculation_route.py:107-141`; terminal origin from the resolver's provenance construction; authoring support is `scaffold` (newmodelo scaffolds the section, no row synthesis) for every kind. Selector model paths are under `src/cadrumo/domain/calculations/registry/`; resolver paths under `src/cadrumo/application/`.

| Provider kind | Authored rows | Provider model | Validator | Runtime owner | Output channel | Terminal origin | Authoring support | Status |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| manual_input | 8012 | `ManualInputSelector` `manual_input_selector.py:122` | family | pseudo-owner | scalar | operator input | scaffold | explicitly non-runtime |
| design_constant | 4 | `DesignConstantSelector` `design_constant_bindings.py:53` | family | pseudo-owner | scalar | constant on selector | scaffold | explicitly non-runtime |
| profile | 128 | `ProfileSelector` `bindings.py:824` | selector-only | `ProfileSourceResolver` pre_mesh | scalar | profile field | scaffold | complete |
| previous_filing | 24 | `PreviousModeloSelector` `bindings_previous_filing.py:445` | family | `PreviousFilingSourceResolver` mesh | scalar | filed casilla observation | scaffold | complete |
| relation_prefill | 105 | `_RelationPrefillSelector` `bindings.py:496` | selector-only | `RelationPrefillSourceResolver` mesh | scalar | filed casilla observation via relation | scaffold | partial: no typed relation ref |
| ledger_iva_aggregation | 499 | `_IvaLedgerSelector` `ledger_iva_bindings.py:187` | family | `LedgerIvaAggregationSourceResolver` mesh | scalar | ledger aggregate | scaffold | complete |
| ledger_oss_aggregation | 5 | `_OssIossLedgerSelector` `ledger_oss_bindings.py:76` | family | `OssIossLedgerSourceResolver` mesh | scalar | ledger aggregate | scaffold | complete |
| ledger_renta_income_aggregation | 10 | `_RentaLedgerIncomeSelector` `ledger_renta_income_bindings.py:35` | family | `LedgerRentaIncomeAggregationSourceResolver` mesh | scalar | ledger aggregate | scaffold | complete |
| ledger_renta_gastos_estimacion_directa_aggregation | 28 | `_RentaLedgerGastosEstimacionDirectaSelector` `ledger_renta_gastos_estimacion_directa_bindings.py:84` | family | `LedgerRentaGastosEstimacionDirectaAggregationSourceResolver` mesh | scalar | ledger aggregate | scaffold | complete |
| ledger_renta_gastos_pago_fraccionado_aggregation | 1 | `_RentaLedgerGastosPagoFraccionadoSelector` `ledger_renta_gastos_pago_fraccionado_bindings.py:54` | family | `LedgerRentaGastosPagoFraccionadoAggregationSourceResolver` mesh | scalar | ledger aggregate | scaffold | complete |
| ledger_impatriado_income_aggregation | 2 | `_ImpatriadoLedgerIncomeSelector` `ledger_impatriado_bindings.py:80` | family | `LedgerImpatriadoIncomeAggregationSourceResolver` mesh | scalar | ledger aggregate | scaffold | complete |
| ledger_irnr_income_aggregation | 2 | `_IrnrLedgerIncomeSelector` `irnr_ledger_bindings.py:44` | family | `LedgerIrnrIncomeAggregationSourceResolver` mesh | scalar + rows | ledger aggregate | scaffold | complete |
| retenciones_aggregation | 15 | `_RetencionesAggregationSelector` `retenciones_bindings.py:82` | family | `RetencionesAggregationSourceResolver` mesh | scalar | retenciones register | scaffold | complete |
| withholding | 203 | `WithholdingSelector` `withholding_bindings.py:518` | family | `WithholdingSourceResolver` mesh | scalar | per-perceptor observation | scaffold | complete |
| payable_invoice / collectible_invoice / m347_third_party_operation | 17 / 17 / 22 | `_InvoiceSelector` `invoice_bindings.py:177` | family | `InvoiceCatalogueSourceResolver` mesh | scalar + rows | invoice catalogue | scaffold | complete |
| ledger_transaction | 0 | `_InvoiceSelector` | family | none | rows | none | scaffold | missing: model without owner |
| purchase_invoice_evidence | 0 | `_InvoiceSelector` | family | none | rows | none | scaffold | missing: model without owner |
| foreign_asset | 6 | `_ForeignAssetSelector` `detail_record_bindings.py:244` | family | `ForeignAssetsAggregationSourceResolver` mesh | rows | detail-record store | scaffold | complete |
| atribucion_member | 38 | `_AtributionSelector` `detail_record_bindings.py:484` | family | `AtribucionMemberSourceResolver` mesh | scalar + rows | profile socios facts | scaffold | complete |
| inventory | 3 | `_InventorySelector` `inventory_bindings.py:54` | family | `InventorySourceResolver` mesh | rows | inventory store | scaffold | partial: selector hard-codes `filing_year = 2025` |
| related_party_operation | 6 | `_RelatedPartySelector` `detail_record_bindings.py:158` | family | none | rows | none | scaffold | missing: authored, no owner |
| refund_operation | 5 | `_RefundSelector` `detail_record_bindings.py:625` | family | none | rows | none | scaffold | missing: authored, no owner |
| donativo_donor | 5 | `_DonativoSelector` `donativo_bindings.py:130` | family | none | rows | none | scaffold | missing: authored, no owner |
| gasto193_contributor | 8 | `_Gasto193Selector` `gasto193_bindings.py:66` | family | none | rows | none | scaffold | missing: authored, no owner |
| withholding296 | 0 | `_Withholding296Selector` `withholding296_bindings.py:132` | family | none | rows | none | scaffold | missing: model without owner |
| iva_compensation_annual_partition | 8 | `_IvaCompensationAnnualPartitionSelector` `bindings.py:576` | selector-only | `IvaCompensationAnnualPartitionSourceResolver` mesh | scalar | derived from filed M303 history | scaffold | complete |
| m303_regimen_simplificado_annual_summary | 40 | `M303RegimenSimplificadoAnnualSummarySelector` `m303_regimen_simplificado_annual_summary_bindings.py:33` | selector-only | `M303RegimenSimplificadoAnnualSummarySourceResolver` conditional | scalar | filed-current M303 4T revision | scaffold | complete |
| prorrata_regularizacion | 10 | `_ProrrataRegularizacionSelector` `bindings.py:759` | selector-only | `ProrrataRegularizacionSourceResolver` post_mesh | scalar | derived calculation | scaffold | complete |
| bienes_inversion_regularizacion | 10 | `_BienesInversionRegularizacionSelector` `bindings.py:567` | selector-only | `BienesInversionRegularizacionSourceResolver` post_mesh | scalar | derived calculation | scaffold | complete |
| borrador / iva_wallet_decision | 0 | none (refused) | none | resolver exists | scalar | AEAT borrador / wallet decision | none | explicitly non-authored (mesh-only) |

Row counts for `ledger_transaction`, `purchase_invoice_evidence`, and `withholding296` come from a raw-TOML grep that found none; a compiled-authority enumeration should confirm before the ADR.

The seven `missing` kinds share one root cause: the enum comment says a calculate request refuses them "until an executable route owns the source", but the refusal exempts ROWS bindings, so authored rows for five of them (24 rows) compile, publish, and reach calculation with no owner and only an advisory `unhandled_binding_source` diagnostic. `src/cadrumo/core/aggregation.py:396-398`; `src/cadrumo/application/modelo/calculation_actions.py:1783-1786`; `src/cadrumo/application/aggregation/source_resolution_operations.py:311-331`. Under the proposed registration authority this becomes a compile-time refusal or an explicit `disposition = "deferred"` on the registration, never a silent runtime gap.

### Runtime resolvers re-read selector fields in fourteen places

A closed provider type only pays off if resolvers consume it as typed members. Today resolvers re-read fields by dict key, `getattr`, or `isinstance`, several with a Mapping-or-model dual path that exists only because the field type admits both. `src/cadrumo/application/modelo/binding_prefill.py:109-141,711-714`; `src/cadrumo/application/calculations/bienes_inversion_regularizacion.py:104-109`; `src/cadrumo/application/calculations/prorrata_regularizacion.py:176,544,559`; `src/cadrumo/application/aggregation/inventory.py:36-38,81`; `src/cadrumo/application/aggregation/foreign_assets.py:81-83`; `src/cadrumo/application/calculations/foreign_asset_redeclaration.py:141`; `src/cadrumo/application/aggregation/oss_ioss.py:347-350`; `src/cadrumo/application/aggregation/modelo_bindings.py:1040`; `src/cadrumo/application/aggregation/iva_ledger.py:1344`; `src/cadrumo/application/aggregation/service.py:278`; `src/cadrumo/application/modelo/profile_binding.py:1344-1349`; `src/cadrumo/application/filing/runtime.py:834`; `src/cadrumo/application/filing/draft_construction.py:848-854`; `src/cadrumo/application/aggregation/_per_grupo_member_keys.py:69-71`. Each is a migration worklist item: replace with a typed narrow on the provider member.

### Temporal-resolution model: one grammar exists, it is owned by the wrong type, and it is declared three times

`PreviousModeloSelector` already carries the full relative grammar with mutual-exclusion validation: `filing_year_delta`, `max_year_delta`, `period`, `source_periods`, `source_period_offset_from_target`, `prior_quarter_expanding_span`. `src/cadrumo/domain/calculations/registry/bindings_previous_filing.py:457-462,552-599`. Coordinate derivation is `expected_year = filing_year + filing_year_delta + period_year_delta` with anchors from `required_period_anchors_for_target`. `bindings_previous_filing.py:157,352,485-504,756-785`. Source revision selection is separate and law-determined: the carry gate re-confirms each observation's stamped revision against `ValidatedRegistryAuthority.inspect_revision`. `src/cadrumo/application/calculations/revision_carry_gate.py:41-60`; `src/cadrumo/application/modelo/binding_prefill.py:150-160`.

The same axes are declared again in `RelationRevisionSelector` (`filing_year_delta` or absolute `year`/`year_from`/`year_to`) and again in `RelationPeriodAlignment` (which has its own `filing_year_delta`). `src/cadrumo/domain/calculations/registry/schema_surfaces.py:768-786,855-885`. The relation therefore carries the delta twice within itself and a third time when the prefill binding restates `source_periods`. The absolute `year` shape on `RelationRevisionSelector` is the one authored surface that admits a concrete source year; the proposed schema refuses it. The inventory selector hard-codes `filing_year = 2025` as an authored field, which is an absolute coordinate in a provider template. `src/cadrumo/domain/calculations/registry/inventory_bindings.py:54`.

Proposed closed temporal union, lifted from `PreviousModeloSelector` and made provider-agnostic:

| Member `kind` | Fields | Derived from |
| --- | --- | --- |
| `same_target_context` | none | default for ledger, profile, manual, constant |
| `same_filing_year_periods` | `source_periods` | `source_periods` with delta 0 |
| `filing_year_offset` | `years`, `source_periods`, optional `max_years` | `filing_year_delta`, `max_year_delta` |
| `target_period_offset` | `periods` (non-zero) | `source_period_offset_from_target` |
| `prior_quarter_expanding_span` | none | `prior_quarter_expanding_span` |
| `filed_current_period` | `source_period` | M303 annual summary's literal `4T` |

Availability states stay runtime-owned and unchanged: `storage_degraded`, empty-but-owned resolution, loud zero with `source_issue`, `unresolved_binding_ids`, pre-activity scope-out. `src/cadrumo/application/aggregation/source_resolution_operations.py:334-362`; `src/cadrumo/application/aggregation/withholding_source.py:100-119`; `src/cadrumo/application/aggregation/source_mesh.py:748-765`; `binding_prefill.py:684-710`.

### Relations boundary: keep separate with a typed reference, or absorb

Evidence for each alternative, without deciding.

Keep separate. Relations carry two things bindings do not: `kind` and `dependency_role` (for example `periodic_to_annual_summary`), and the runtime keys a `Mapping[RelationId, BindingId]` join. `schema_surfaces.py:896-897,917-934`; `src/cadrumo/application/calculations/relation_prefill.py:810,921`. The grouping type `dict[BindingId, tuple[RelationDefinition, ...]]` admits several relations per target binding, resolved only by a loader diagnostic. `src/cadrumo/domain/calculations/registry/queries.py:769`; `schema.py:581`. If kept, `RelationPrefillProvider` must carry `relation_id: RelationId`, the compiler must validate the closure both ways, the relation must drop its own temporal grammar in favour of the binding's `temporal` member, and relations must inherit by identifier under the edition decision exactly as bindings do, with a `relation_evolutions` section to follow.

Absorb. Every relation field except `kind` and `dependency_role` is already a provider-template or temporal field. `schema_surfaces.py:898-906`. Absorbing yields one `RelationPrefillProvider { kind, dependency_role, source_modelo, source_casilla_ids, temporal, aggregation }` and deletes `relations/*.toml`, `RelationRevisionSelector`, `RelationPeriodAlignment`, `_validate_dependency_sections`, and the relation-id join. The 105 authored prefill bindings and their relations would merge one-to-one; the compiler guarantees uniqueness only diagnostically, so the migration must first prove no binding has two relations. Independent reuse of a relation by more than one binding was not found in the corpus but was not exhaustively measured.

Duplication is the decisive observation: source modelo, source casilla, source periods, period offset, filing-year delta, and aggregation are each declared on both sides today. The edition decision makes absorption cheaper because it removes the need for a second inheritance family.

### Proposed authored TOML, adjusted for the edition decision

```toml
[[bindings]]
id = "renta-base-liquidable-negativa-general-anterior"
value = { data_type = "money", channel = "decimal" }
aggregation = { op = "copy" }
applicability = { kind = "target_periods", periods = ["0A"] }
terminal_origins = [
  { source_class = "filed_modelo_casilla", role = "primary", cardinality = "exactly_one", fingerprint = "required" },
]
authorship = { kind = "authored" }
legal_refs = ["ley-35-2006:art-50"]

[bindings.provider]
kind = "previous_filing"
source_modelo = "100"
source_casilla_ids = ["1391"]
temporal = { kind = "filing_year_offset", years = -1, source_periods = ["0A"] }
```

Changes from the draft in the task brief: `semantic_lineage` is removed because identity is the identifier and `replaced`/`retired` rows live in `binding_evolutions/*.toml`; `source_refs` is omitted when it equals the manifest default; the table header is section-relative because fragment files carry no revision prefix under the fragment grammar. `dev/registry/compiler/_loader_revision_fragments.py:121-127`.

### Proposed normalized Python shape

```python
class BindingDefinition(RegistryModel):
    id: BindingId
    provider: BindingProvider
    value: BindingValueContract
    aggregation: BindingAggregation
    applicability: BindingApplicability = AllRevisionContexts()
    terminal_origins: tuple[TerminalOriginExpectation, ...]
    authorship: BindingAuthorship = AuthoredBinding()
    aeat_prefilled: bool = False
    legal_refs: LegalRefs
    source_refs: SourceRefs
    source_citations: tuple[SourceCitation, ...] = ()

BindingProvider = Annotated[
    ManualInputProvider | DesignConstantProvider | ProfileProvider
    | PreviousFilingProvider | RelationPrefillProvider
    | LedgerIvaProvider | LedgerOssProvider | LedgerRentaIncomeProvider | ...
    | WithholdingProvider | InvoiceProvider | ForeignAssetProvider | ...,
    Field(discriminator="kind"),
]

class BindingValueContract(RegistryModel):
    data_type: BindingDataType          # money | integer | boolean | text | date | enum | rows
    channel: BindingValueChannel        # decimal | integer | boolean | text | date | enum | row_set
    typed_enum: BindingTypedEnumKind | None = None
    row_grouping: RowSetGrouping | None = None   # required iff channel == row_set

class TerminalOriginExpectation(RegistryModel):
    source_class: TerminalOriginClass    # operator_input | design_constant | profile_field | filed_modelo_casilla | ledger_aggregate | invoice_catalogue | perceptor_observation | detail_record | derived_calculation
    role: CalculationSourceLineageRole   # PRIMARY | CONTRIBUTOR (existing enum)
    cardinality: Literal["exactly_one", "at_least_one", "zero_or_more"]
    fingerprint: Literal["required", "optional"]

class BindingProviderRegistration(RegistryModel):
    kind: BindingSourceKind
    provider_model: type[BaseModel]
    validator: BindingProviderValidator
    permitted_value_channels: frozenset[BindingValueChannel]
    permitted_aggregation_ops: frozenset[BindingAggregationOp]
    permitted_terminal_origins: frozenset[TerminalOriginClass]
    output: Literal["scalar", "rows", "scalar_and_rows"]
    disposition: Literal["filing_grade", "advisory", "deferred", "non_runtime"]
    route: RouteOwnership | NonRuntimeOwnership   # resolver id + stage, or pseudo-owner
    authoring: Literal["scaffold", "generator", "none"]
```

`BindingSourceKind` survives as the `kind` literal set for the runtime mesh and the route table; the mesh-only members are simply not union members. `typed_enum`, `row_grouping`, and the existing `ROW_SET_GROUPING_FOR_BINDING_SOURCE` map fold into the value contract and the registration rather than staying as sibling fields and a core-level dict. `schema.py:268`; `src/cadrumo/core/aggregation.py:411-420`.

The registration table is the single defining module; `selector_model_for_source`, `_BINDING_VALIDATOR_REGISTRY`, and `_CANONICAL_RESOLVER_STAGES` become derived views or are deleted. The import-time route invariants (unique resolver, one owner per kind, complete coverage) already exist and move onto the registration. `calculation_route.py:265-295`. The facts compiler's provider-registration seam is the implementation pattern. `dev/registry/compiler/fact_providers.py:52-136`.

Compiler refusals derived from it: unregistered `kind`; registration without model or validator; runtime disposition without a route; `value.channel` not in `permitted_value_channels`; `aggregation.op` not permitted or `rows` op with a scalar channel; `terminal_origins` naming a class the registration cannot produce; a `temporal` member with an absolute year; a relation reference that does not close; `authorship.kind = "generated"` without generator identity; a BOUND casilla whose primary or alternates name a `deferred` provider; alternates whose `value` differs from the primary's; a binding referenced by no typed consumer unless `applicability` carries an explicit non-calculation disposition.

### Authored, compiled, and runtime ownership

Authored: everything in the TOML above plus `binding_evolutions` rows. Compiler-derived: occurrence coordinate, whether the row is declared or inherited and from which edition, fragment path and ordinal, declaration fingerprint, registration identity, reverse consumer index (casillas, formulas, exports, relations), generator-run digest, diagnostics. Runtime: target filing context, selected target revision, resolved source coordinates and revision, resolver id, actual terminal nodes with `lineage_role`, fingerprints, disposition, diagnostics; `CalculationSourceProvenance` already has these fields. `src/cadrumo/application/aggregation/source_mesh.py:618-646`. The design adds a check that the resolved `contributor_source_kind` and origin class fall inside the authored `terminal_origins` expectation, which is what makes the expectation auditable rather than decorative.

### Authoring and generation tools

`dev/registry/newmodelo` scaffolds `bindings/` and instructs edition-free ids but synthesizes no rows. `dev/registry/newmodelo/manager.py:79,280-283`; `dev/registry/newmodelo/checklist.py:78-83`. `edition_delta_migration.py` is casilla-only and duplicates the reference-section map held by the loader. `dev/registry/edition_delta_migration.py:85,162-165`; `dev/registry/compiler/_loader_internals.py:102-106`. `rename_formula_binding_identifiers.py` is the only in-place binding rewriter and carves out modelos 185, 222, 347 and 390. `dev/registry/rename_formula_binding_identifiers.py:1-60`. No generator writes `bindings/*.toml` and no generated-lineage marker exists on bindings; only the export tree carries `_generation.provenance.json`. `dev/registry/compiler/loader_cache.py:89,386`. The `authorship` member is therefore currently always `authored`; the ADR should decide whether `generated` ships now or the union stays single-member.

### Temporally coupled ids: 756 audit candidates, zero period tokens

756 of 4312 ids embed a year in the modelo-version prefix (`modelo-232-2016.*` 185, `modelo-232-2018.*` 185, `modelo-353-2021.*` 166, `modelo-360-2010.*` 158, `modelo-720-2013.*` 44); 18 `modelo-714` matches are column offsets, not years. No id contains a period token. The rename tool skips the 232 pair because `2016` is not a whole segment of revision id `2016-2017`, yet the two 232 sets have byte-identical suffixes. `rename_formula_binding_identifiers.py:16-20`. That identity is a candidate, not a proof: the migration must show each pair shares provider shape, consumers, and legal grounding before merging under the edition-free id; where it does, the inheritance decision makes the second set a pure restatement to delete.

### Migration worklist, grouped by root cause

Hotspot A, open type: replace `source + selector` with `provider`; delete `BindingSelector`, `BindingSelectorMap`, `BindingSelectorValue`, `_coerce_selector`, `_validate_selector_shape`, and the three "discriminated" docstrings; rewrite the query projection to serialize the typed member. Owner: registry schema.

Hotspot B, split enrollment: introduce `BindingProviderRegistration`; derive or delete the selector, validator, and route tables; move route invariants onto it; classify the seven unowned kinds as `deferred` or give them owners; remove the ROWS exemption from the novel-source refusal in favour of the registration disposition. Owner: registry compiler plus application route.

Hotspot C, selector re-reading: fourteen resolver sites narrow on typed members. Owner: application resolvers, one writer per file.

Hotspot D, temporal grammar: lift the `PreviousModeloSelector` grammar into the shared `temporal` union; delete the `RelationRevisionSelector` absolute-year shape and `RelationPeriodAlignment.filing_year_delta`; remove `filing_year = 2025` from the inventory selector. Owner: registry schema.

Hotspot E, relations: decision-dependent.

Hotspot F, corpus: rewrite 9235 rows to the new shape in one hard cut (the rename tool is the pattern), then apply the inheritance decision to drop restated rows once the materialiser merges bindings; adjudicate the 756 year-bearing ids. Owner: registry corpus, sequenced after the casilla migration in flight.

Hotspot G, documentation debt: the checked-but-deferred plan step, the TUI reference claim, and the `newmodelo` checklist wording. Owner: vault curation.

### Unresolved ADR decisions

Relations kept with a typed reference versus absorbed. Terminal-origin class vocabulary and whether contributor origins are declared or derived. Value channel set, in particular whether text, date, and boolean need distinct channels beyond the existing decimal, enum, date, and row maps. Whether `applicability` needs an explicit non-calculation member for bindings with no typed calculation consumer. Whether `authorship = generated` ships now. Disposition of the seven unowned kinds: deferred registration or route implementation. Sequencing of the corpus cut relative to the in-flight casilla materialiser and the per-modelo migration wave.

### Not investigated

Compiled-authority enumeration of binding rows per kind was not run because the checkout's authority is stale relative to the authored tree; counts above are raw-TOML counts. Exhaustive relation reuse was not measured. Per-pair semantic equivalence of the 756 year-bearing ids was not adjudicated.

## Sources

- `dev/registry/compiler/_loader_internals.py:102-106,712-825,1104,1137`
- `dev/registry/compiler/loader_grammar.py:17-34`
- `dev/registry/compiler/_loader_revision_fragments.py:107-127`
- `dev/registry/compiler/loader.py:60`
- `dev/registry/compiler/loader_cache.py:89,386`
- `dev/registry/compiler/fact_providers.py:52-136`
- `dev/registry/compiler/_validate_record_sections.py:124-128`
- `dev/registry/compiler/validate_formulas.py:121-122`
- `dev/registry/compiler/validate_exports.py:393,435-436`
- `dev/registry/compiler/_validate_dependency_sections.py:70-71`
- `dev/registry/compiler/_validate_export_exemption.py:161`
- `dev/registry/edition_delta_migration.py:85,162-165`
- `dev/registry/rename_formula_binding_identifiers.py:1-60`
- `dev/registry/newmodelo/manager.py:79,280-283`
- `dev/registry/newmodelo/checklist.py:78-83`
- `dev/docs/casilla_reference.py:606`
- `src/cadrumo/domain/calculations/registry/schema.py:258-435,581`
- `src/cadrumo/domain/calculations/registry/schema_scalars.py:503-515`
- `src/cadrumo/domain/calculations/registry/schema_surfaces.py:283-343,376-387,481-490,768-786,855-934`
- `src/cadrumo/domain/calculations/registry/schema_formula.py:150-176`
- `src/cadrumo/domain/calculations/registry/schema_exports.py:111,464,830-884`
- `src/cadrumo/domain/calculations/registry/bindings.py:425-450,496-530,567,576,759,824,889-1078`
- `src/cadrumo/domain/calculations/registry/bindings_previous_filing.py:157,352,445-504,552-599,756-785`
- `src/cadrumo/domain/calculations/registry/binding_targets.py:22,31`
- `src/cadrumo/domain/calculations/registry/detail_record_bindings.py:158,244,324-567,625`
- `src/cadrumo/domain/calculations/registry/inventory_bindings.py:54`
- `src/cadrumo/domain/calculations/registry/query_reports.py:155-263`
- `src/cadrumo/domain/calculations/registry/queries.py:769,966-1010`
- `src/cadrumo/domain/calculations/registry/identifier_lineage.py:27-46`
- `src/cadrumo/domain/calculations/registry/facts/schema.py:376-384`
- `src/cadrumo/domain/calculations/registry/facts/resolution.py:121,216`
- `src/cadrumo/domain/calculations/registry/authority_artifact.py:407`
- `src/cadrumo/core/aggregation.py:220-227,348-420`
- `src/cadrumo/application/modelo/calculation_route.py:107-141,265-295`
- `src/cadrumo/application/modelo/calculation_actions.py:1781-1792`
- `src/cadrumo/application/modelo/binding_prefill.py:109-160,601-714`
- `src/cadrumo/application/modelo/profile_binding.py:1344-1349`
- `src/cadrumo/application/aggregation/source_mesh.py:281-356,618-646,748-765`
- `src/cadrumo/application/aggregation/source_resolution_operations.py:311-362`
- `src/cadrumo/application/aggregation/modelo_bindings.py:809,1040,1048`
- `src/cadrumo/application/aggregation/iva_ledger.py:1344,1350`
- `src/cadrumo/application/aggregation/withholding_source.py:100-119`
- `src/cadrumo/application/aggregation/foreign_assets.py:81-83,364,488`
- `src/cadrumo/application/aggregation/atribucion_member.py:116-117`
- `src/cadrumo/application/aggregation/inventory.py:36-38,81,206`
- `src/cadrumo/application/aggregation/oss_ioss.py:347-350`
- `src/cadrumo/application/aggregation/service.py:278`
- `src/cadrumo/application/aggregation/_per_grupo_member_keys.py:69-71`
- `src/cadrumo/application/invoices/source_resolver.py:248`
- `src/cadrumo/application/calculations/relation_prefill.py:810,921`
- `src/cadrumo/application/calculations/revision_carry_gate.py:41-60`
- `src/cadrumo/application/calculations/bienes_inversion_regularizacion.py:104-109`
- `src/cadrumo/application/calculations/prorrata_regularizacion.py:176,544,559`
- `src/cadrumo/application/calculations/foreign_asset_redeclaration.py:141`
- `src/cadrumo/application/filing/runtime.py:834`
- `src/cadrumo/application/filing/draft_construction.py:848-854`
- `.vault/adr/2026-09-09-registry-edition-authoring-adr.md:92-135`
- `.vault/plan/2026-06-26-binding-vocabulary-cli-cohesion-plan.md:107-117`
- `.vault/reference/2026-08-25-tui-architecture-s127-workspace-field-manifest-reference.md:54`
