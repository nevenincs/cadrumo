---
generated: true
tags:
  - '#index'
  - '#binding-vocabulary-cli-cohesion'
date: '2026-08-16'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:803de087744673ee65e9e68425b2353cd9ab0a898affe35b21035210323f2155'
related:
  - '[[2026-06-26-binding-vocabulary-cli-cohesion-adr]]'
  - '[[2026-06-26-binding-vocabulary-cli-cohesion-plan]]'
  - '[[2026-06-26-binding-vocabulary-cli-cohesion-reference]]'
  - '[[2026-07-02-binding-vocabulary-cli-cohesion-audit]]'
  - '[[2026-07-04-binding-vocabulary-cli-cohesion-audit]]'
  - '[[2026-07-05-binding-vocabulary-cli-cohesion-research]]'
---

# `binding-vocabulary-cli-cohesion` feature index

Auto-generated index of all documents tagged with `#binding-vocabulary-cli-cohesion`.

## Documents

### adr

- `2026-06-26-binding-vocabulary-cli-cohesion-adr` - `binding-vocabulary-cli-cohesion` adr: `vocabulary and CLI cohesion: retire the binding homonyms and reconcile the source-pull verb surface` | (**status:** `accepted`)

### audit

- `2026-07-02-binding-vocabulary-cli-cohesion-audit` - `binding-vocabulary-cli-cohesion` audit: `Wave 1 D9 close-blocker audit`
- `2026-07-04-binding-vocabulary-cli-cohesion-audit` - `binding-vocabulary-cli-cohesion` audit: `S23/S24 evidence review`

### exec

- `2026-06-26-binding-vocabulary-cli-cohesion-W01-P01-S01` - Rename BindingRowPayload to BindingListRowPayload as one atomic relocation:BindingRowPayload commit, sweeping the def, __all__, ModeloBindingsListResult.bindings, the _modelo_discovery_cli import, _binding_list_rows_for_report uses, and the test docstring
- `2026-06-26-binding-vocabulary-cli-cohesion-W01-P01-S02` - Rename ModeloBindingRow to ModeloBindingQueryRow as one atomic relocation:ModeloBindingRow commit, sweeping the def, the rows tuple field, the _binding_rows builder, registry __all__, the registry package __init__ re-export, and the _schema.py docstring-core-struct xref
- `2026-06-26-binding-vocabulary-cli-cohesion-W01-P01-S03` - Assert BindingPreviewRowPayload (A2) and _BindingRow (A4) are already role-distinct / module-private at HEAD and confirm no bare BindingRow stem collision remains
- `2026-06-26-binding-vocabulary-cli-cohesion-W01-P01-S04` - Verify W01.P01 no-shift: run pytest --collect-only -q clean, the docstring-core-struct gate green, and the bindings-framework gate suite green
- `2026-06-26-binding-vocabulary-cli-cohesion-W01-P02-S05` - Re-home _m232_row_bindings.py to a row-materialisation module name dropping the _bindings stem (e.g. _m232_row_materialisation.py) toward the domain row-model surface as one atomic relocation:m232-row-materialisation commit
- `2026-06-26-binding-vocabulary-cli-cohesion-W01-P02-S06` - Rename _sources.py to a corpus-catalogue module name (e.g. _corpus_catalogue.py) as one atomic relocation:corpus-catalogue commit
- `2026-06-26-binding-vocabulary-cli-cohesion-W01-P02-S07` - Verify W01.P02 no-shift: run pytest --collect-only -q clean, dev.docs.apidocs scaffold --check clean (no orphan / missing stubs), and the catalogue-verification / m232-row test consumers green
- `2026-06-26-binding-vocabulary-cli-cohesion-W02-P03-S08` - Rename ModeloReconciliationSourceKind to ModeloReconciliationEvidenceKind (reconcile transport / external-evidence axis, NOT folded into BindingSourceKind) as one atomic relocation:ModeloReconciliationSourceKind commit, sweeping all 30 occurrences across the reconcile CLI, the application modelo __init__ re-export, _reconcile.py, _justificante.py, and the two test modules
- `2026-06-26-binding-vocabulary-cli-cohesion-W02-P03-S09` - Rename the BusinessOperationInvoiceSourceKind TYPE to BusinessOperationInvoiceDirection (invoice-direction axis) KEEPING the payable_invoice / collectible_invoice member STRING values load-bearing per aeat-spanish-stem-naming, as one atomic relocation:BusinessOperationInvoiceSourceKind commit, sweeping all 31 occurrences across the ledger invoice CLI, the invoices _source_resolver, _business_operation_invoice.py, the ledger __init__ re-export, and the two test modules
- `2026-06-26-binding-vocabulary-cli-cohesion-W02-P03-S10` - Rename the IvaCompensationAuthoritySourceKind type alias (Literal, not a class) to IvaCompensationAuthorityKind (wallet/compensation authority axis) as one atomic relocation:IvaCompensationAuthoritySourceKind commit, sweeping the def, the two field annotations, __all__, and the docs/conf.py nitpicky-resolver allowlist
- `2026-06-26-binding-vocabulary-cli-cohesion-W02-P03-S11` - Verify W02.P03 no-shift: run pytest --collect-only -q clean, the reconcile / ledger-invoice / iva-compensation test modules green, and assert the C2 member string values payable_invoice / collectible_invoice are unchanged
- `2026-06-26-binding-vocabulary-cli-cohesion-W02-P04-S12` - Rename the PerModeloAggregationProvider role-family to a name that says aggregation provider role (e.g. PerModeloAggregationContributor) for both PerModeloAggregationProvider and PerModeloAggregationProviderContract as one atomic relocation:PerModeloAggregationProvider commit, sweeping the enum, the contract model, the provider field / providers tuple, and the ~12 consumer sites
- `2026-06-26-binding-vocabulary-cli-cohesion-W02-P04-S13` - Rename the schema-provider role-family (RegistrySchemaProvider / CasillaSchemaProvider) to a name that says schema source / accessor distinct from the settled resolver port, as one atomic relocation:RegistrySchemaProvider commit, sweeping the class def, builder returns, __all__, and the ~6 consumer sites in filing runtime
- `2026-06-26-binding-vocabulary-cli-cohesion-W02-P04-S14` - Verify W02.P04 no-shift: run pytest --collect-only -q clean, the aggregation / filing-runtime test modules green, and assert ModeloSourceResolver / CalculationSourceResolution / merge_source_resolutions were NOT renamed (the phase-2.2 settled contract is intact)
- `2026-06-26-binding-vocabulary-cli-cohesion-W03-P06-S19` - Assert and document the three prefill tiers are distinct and not merged: relation prefill (_relation_prefill.py, RelationPrefillSourceResolver), previous-filing direct carry (_binding_prefill.py), and AEAT borrador pre-fill (registry _schema.py aeat_prefilled / borrador-fed typed_enum)
- `2026-06-26-binding-vocabulary-cli-cohesion-W03-P06-S20` - Verify W03.P06 no-shift: run pytest --collect-only -q clean and assert the prefill modules retain distinct names and tiers with no merge and no behaviour change (docstring-only clarification)
- `2026-06-26-binding-vocabulary-cli-cohesion-W05-P08-S25` - Replace DataBindingDefinition.selector with the BindingSourceKind selector union
- `2026-06-26-binding-vocabulary-cli-cohesion-W05-P08-S26` - DEFERRED FOLLOW-UP (paired with the selector union): narrow the typed_enum stringly-typed pointer (str-or-None enum class name) on DataBindingDefinition to a typed enum-class reference, sweeping the bindings list CLI table, the ModeloBindingQueryRow projection, the borrador resolver, and the Sheets-pull router
- `2026-06-26-binding-vocabulary-cli-cohesion-W03-P05-S15` - Prefix the ledger-aggregation-tier Observation carriers with a consistent domain prefix (IvaLedgerObservation, OssIossLedgerObservation, RetencionObservation, CounterpartObservation, CounterpartAggregationObservation, ForeignAssetIngestObservation, RentaDeductibleExpenseObservation, the detail-record family RelatedPartyOperationObservation / Modelo720RowObservation / AtributionMemberObservation / RefundOperationObservation, WithholdingObservation, InvoiceObservation), one atomic relocation commit per renamed carrier tagged relocation:<symbol>, each regenerating docs-scaffold + API-stub + docstring-core-struct in the same commit
- `2026-06-26-binding-vocabulary-cli-cohesion-W03-P05-S16` - Prefix the live-capture / sede-tier Observation carriers where the bare stem collides (FiledDeclaracionObservation, IvaCompensationWalletObservation, NifIvaCheckObservation, DeclaracionObservation, BorradorObservation), one atomic relocation commit per renamed carrier tagged relocation:<symbol>, each regenerating docs-scaffold + API-stub + docstring-core-struct in the same commit
- `2026-06-26-binding-vocabulary-cli-cohesion-W03-P05-S17` - Prefix the oracle-tier Observation carriers where the bare stem collides (RentaWebOpenObservation, GroiObservation, AeatNifIvaObservation
- `2026-06-26-binding-vocabulary-cli-cohesion-W03-P05-S18` - Verify W03.P05 no-shift: run pytest --collect-only -q clean, the affected aggregation / sede / oracle test modules green, and assert the calc/registry-tier anchor carriers (CasillaObservation, RegistryModeloObservation) and all role-suffixed *ObservationRequirement / *Repository / *Store / *Protocol names were NOT renamed
- `2026-06-26-binding-vocabulary-cli-cohesion-W04-P07-S21` - OPERATOR-VISIBLE: rename the bindings preview verb (G1) to a value-bearing name that says what it sources rather than the UI gesture, under aeat-cli-pull-and-file-standard, as one atomic commit
- `2026-06-26-binding-vocabulary-cli-cohesion-W04-P07-S22` - OPERATOR-VISIBLE: reconcile the calc pull --compute verb (G2) with the one produce-bound-casilla-values-from-sources story, separating the Sheets-transport pull from the compute multiplexing per aeat-cli-pull-and-file-standard, as one atomic commit
- `2026-06-26-binding-vocabulary-cli-cohesion-W04-P07-S23` - OPERATOR-VISIBLE: align the work calculate verb (G3, the canonical aggregation-engine entry) name to the reconciled one-verb story per aeat-cli-pull-and-file-standard, as one atomic commit
- `2026-06-26-binding-vocabulary-cli-cohesion-W04-P07-S24` - Verify W04.P07 no-shift: run pytest --collect-only -q clean, test_documented_command_conformance.py and test_json_schema_conformance.py green, the locale parity + honesty gates green, and assert no dead operator instruction remains (write-policy allowlist, default_suggestion, next_action, operator help, and command= identifiers all reference the reconciled verb)
- `2026-06-26-binding-vocabulary-cli-cohesion-W05-P08-S27` - DEFERRED FOLLOW-UP verification: when F8 lands, run pytest --collect-only -q clean, test_schema_hygiene.py and the bindings-framework gate suite green, and assert the selector union is behaviour-preserving over the prior validate-time selector models

### plan

- `2026-06-26-binding-vocabulary-cli-cohesion-plan` - `binding-vocabulary-cli-cohesion` plan

### reference

- `2026-06-26-binding-vocabulary-cli-cohesion-reference` - `binding-vocabulary-cli-cohesion` reference: `phase-2.4 rename and re-home anchors: binding homonyms, CLI verb fork, selector typing`

### research

- `2026-07-05-binding-vocabulary-cli-cohesion-research` - `binding-vocabulary-cli-cohesion` research: `closure grounding inventory`
