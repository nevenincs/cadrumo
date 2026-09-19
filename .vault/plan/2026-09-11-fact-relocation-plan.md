---
tags:
  - '#plan'
  - '#fact-relocation'
date: '2026-09-11'
tier: L3
related:
  - '[[2026-09-09-facts-registry-governed-fact-catalogue-adr]]'
  - '[[2026-09-11-fact-relocation-research]]'
modified: '2026-09-11'
body_schema: body-v2
body_hash: 'sha256:94ccf7b580d8661e52a20a3d6da4afa296dca25cde0f4ec46355be866c4e1e8e'
---

# `fact-relocation` plan

Relocate residual filing-affecting declarations into the existing registry authority while retaining reusable Python mechanics.

## Description

This campaign executes the placement boundary in the amended `2026-09-09-facts-registry-governed-fact-catalogue-adr`, grounded by `2026-09-11-fact-relocation-research`. W01 reconciles the mechanical audit with the active facts-registry campaign. W02 assigns six concurrent Luna/max agents to disjoint declaration families. W03 integrates their results through the existing compiler and authority-artifact publication path.

Only filing-affecting legal and modelo declarations move into existing registry families under `src/cadrumo/_data/registry/aeat`. Python remains responsible for parsing, evaluation, date arithmetic, aggregation execution, evidence reduction, row materialisation, serialisation, resolver dispatch, and workflow. The campaign introduces no second registry, provider, loader, evaluator, gate family, or opaque generic mapping. Unsupported schema shapes are recorded for a separate evidence-backed ADR rather than forced into TOML.

## Steps

## Wave `W01` - prerequisite census and overlap reconciliation

Convert the mechanical audit into a declaration-level migration ledger, reconcile every candidate with existing facts-registry work, and establish disjoint ownership for the six execution lanes. Wave W02 cannot begin until this census is closed.

### Phase `W01.P01` - freeze census and assign lane ownership

Track the census in tmp/fact-relocation/W01-census-ledger.md, prerequisites in W01-prerequisites.md, and ownership in W02-lane-boundaries.md. No production or registry data changes are allowed. Complete when every candidate has a declaration-level disposition, existing-plan overlap, destination family, dependency, owner, and retirement condition.

- [ ] `W01.P01.S01` - Freeze the audited file universe and grouped finding counts as campaign intake; `tmp/mechanical_audit_manifest.md`.
- [ ] `W01.P01.S02` - Normalize every grouped finding into a declaration-level disposition ledger; `tmp/mechanical_audit_findings_index.md`.
- [ ] `W01.P01.S03` - Reconcile candidates against completed and open facts-registry plan rows; `.vault/plan/2026-09-09-facts-registry-plan.md`.
- [ ] `W01.P01.S04` - Map each residual declaration to an existing registry family or an explicit schema gap; `tmp/mechanical_registry_map.md`.
- [ ] `W01.P01.S05` - Partition residual ownership into six non-overlapping lane scopes; `tmp/fact-relocation/W02-lane-boundaries.md`.
- [ ] `W01.P01.S06` - Record evidence publication and schema prerequisites for every lane; `tmp/fact-relocation/W01-prerequisites.md`.

## Wave `W02` - six concurrent Luna/max declaration lanes

Run six disjoint Luna/max phases after W01. Each phase owns one declaration family and lane ledger; Python mechanics remain in place while filing-affecting declarations move through existing registry families.

### Phase `W02.P02` - lane 1 - formulas parameters and applicability

Owner: Luna/max agent 1. Track tmp/fact-relocation/W02-P02-formulas-ledger.md. Own only formula trees, statutory parameters, thresholds, dated windows, and applicability. Exclude bindings, detail schemas, verification, tables, evaluators, and retirement gates. Complete when each item is canonical, relocated through an existing typed family, or explicitly deferred with evidence and no Python legal duplicate.

- [ ] `W02.P02.S07` - Reconcile and relocate residual DT12 and SAL formula declarations; `src/cadrumo/domain/modelos/dt12_reduccion.py and src/cadrumo/domain/modelos/sal_reserva_especial.py`.
- [ ] `W02.P02.S08` - Relocate residual Modelo 303 simplified-regime coefficients reductions and floor expressions; `src/cadrumo/application/calculations/m303_regimen_simplificado.py`.
- [ ] `W02.P02.S09` - Relocate residual Art. 109 and M210 threshold and rate declarations; `src/cadrumo/application/modelo/_art109_activity_income.py and src/cadrumo/application/modelo/_m210_rate.py`.
- [ ] `W02.P02.S10` - Relocate residual annual settlement and compensation-window applicability; `src/cadrumo/domain/iva/m303_settlement.py and src/cadrumo/domain/iva_compensation/balance.py`.
- [ ] `W02.P02.S11` - Reconcile prorrata arithmetic ownership without moving evidence reduction; `src/cadrumo/application/calculations/prorrata_regularizacion.py`.
- [ ] `W02.P02.S12` - Relocate residual maritime cap fraction and eligibility declarations; `src/cadrumo/domain/renta/maritime_exemption.py`.
- [ ] `W02.P02.S13` - Classify insurance and objective-estimation bounds with explicit evidence outcomes; `src/cadrumo/domain/contribuyente/seguro_enfermedad_insured.py and src/cadrumo/application/modelo/_objective_estimation_advisory.py`.
- [ ] `W02.P02.S14` - Close the formula lane ledger with compiled authority and duplicate-retirement evidence; `tmp/fact-relocation/W02-P02-formulas-ledger.md`.

### Phase `W02.P03` - lane 2 - bindings relations and aggregation metadata

Owner: Luna/max agent 2. Track tmp/fact-relocation/W02-P03-bindings-ledger.md. Own source and target casillas, projections, relation instances, period alignment, and model-specific aggregation metadata. Exclude formulas, detail fields, verification, tables, and resolver mechanics. Complete when each edge has one registry owner and Python contains only reusable routing or aggregation behavior.

- [ ] `W02.P03.S15` - Relocate M130-to-M100 projection endpoints and first-slice routing maps; `src/cadrumo/application/modelo/projection.py and src/cadrumo/domain/renta/_first_slice_routing.py`.
- [ ] `W02.P03.S16` - Relocate prorrata and investment regularisation sources targets and annual relations; `src/cadrumo/application/calculations/prorrata_regularizacion.py and src/cadrumo/application/calculations/bienes_inversion_regularizacion.py`.
- [ ] `W02.P03.S17` - Relocate calculation-adjustment and input binding declarations; `src/cadrumo/application/modelo/_calculation_modelo_adjustments.py and src/cadrumo/application/modelo/calculate_input.py`.
- [ ] `W02.P03.S18` - Relocate IVA invoice and renta ledger category routing declarations; `src/cadrumo/application/aggregation`.
- [ ] `W02.P03.S19` - Relocate IVA compensation sources targets periods and carry relations; `src/cadrumo/domain/iva_compensation and src/cadrumo/application/calculations/iva_compensation_casillas.py`.
- [ ] `W02.P03.S20` - Relocate M303-to-M390 handoff and M303 transition and disposition metadata; `src/cadrumo/domain/modelos/calculation_revision_m303_handoff.py and src/cadrumo/application/calculations/m303_carry_ingress.py`.
- [ ] `W02.P03.S21` - Relocate the M202 previous-period relation and initial-value semantics; `src/cadrumo/application/calculations/relation_prefill_m202.py`.
- [ ] `W02.P03.S22` - Close the binding lane ledger with one registry owner per source-target edge; `tmp/fact-relocation/W02-P03-bindings-ledger.md`.

### Phase `W02.P04` - lane 3 - detail records model declarations and export layouts

Owner: Luna/max agent 3. Track tmp/fact-relocation/W02-P04-detail-export-ledger.md. Own row capacity, identity, fields, record families, model declarations, export maps, and layout metadata. Exclude materializers, parsers, serializers, formulas, and verification. Complete when declarations resolve from selected authority and no ordinary Python module duplicates a filing schema.

- [ ] `W02.P04.S23` - Relocate M200 and M296 record-kind collection declarations; `src/cadrumo/application/filing/_m200_projection.py and src/cadrumo/application/filing/_m296_projection.py`.
- [ ] `W02.P04.S24` - Relocate M232 row capacity field identity and binding declarations; `src/cadrumo/domain/modelos/m232_row_materialisation.py`.
- [ ] `W02.P04.S25` - Relocate M720 and M721 foreign-asset detail declarations; `src/cadrumo/application/calculations/foreign_asset_redeclaration.py`.
- [ ] `W02.P04.S26` - Relocate M100 XML block sign-field and export layout declarations; `src/cadrumo/application/filing/_export_xml_dictionary.py`.
- [ ] `W02.P04.S27` - Relocate row-model and Anexo D record-design declarations; `src/cadrumo/domain/modelos/row_models.py and src/cadrumo/domain/contribuyente/inventory/_anexo_d_records.py`.
- [ ] `W02.P04.S28` - Relocate adjustment detail owners and M303 amendment revision metadata; `src/cadrumo/application/modelo/_calculation_modelo_adjustments.py and src/cadrumo/domain/modelos/calculation_revision_amendment.py`.
- [ ] `W02.P04.S29` - Close the detail and export lane ledger with published selected-revision resolution; `tmp/fact-relocation/W02-P04-detail-export-ledger.md`.

### Phase `W02.P05` - lane 4 - verification and reconciliation declarations

Owner: Luna/max agent 4. Track tmp/fact-relocation/W02-P05-verification-ledger.md. Own model-specific expectations, predicate operands, tolerances, implication targets, reason codes, and legal references. Exclude predicate execution, formulas, operational relations, and tables. Complete when each rule is typed and authority-backed while diagnostics and evaluation remain Python.

- [ ] `W02.P05.S30` - Relocate DT12 Art. 20 and Art. 52 verification declarations; `src/cadrumo/application/modelo/_dt12_advisory.py and src/cadrumo/application/modelo/_art20_advisory.py and src/cadrumo/application/modelo/_art52_advisory.py`.
- [ ] `W02.P05.S31` - Relocate M303-to-M349 reconciliation operands tolerance and references; `src/cadrumo/application/modelo/_m303_m349_reconcile.py`.
- [ ] `W02.P05.S32` - Relocate M349 detail obligation and M720 redeclaration predicates; `src/cadrumo/application/modelo/_m349_ledger_guard.py and src/cadrumo/application/modelo/_m720_redeclaration_gate.py`.
- [ ] `W02.P05.S33` - Relocate model-specific cross-period verification instances and reason codes; `src/cadrumo/application/modelo/_verification_cross_period.py and src/cadrumo/application/modelo/_verification_predicates.py`.
- [ ] `W02.P05.S34` - Relocate descendant cardinality and M131 implication declarations; `src/cadrumo/application/modelo/_minimo_descendientes_advisory.py and src/cadrumo/application/modelo/_prior_payment_advisory.py`.
- [ ] `W02.P05.S35` - Close the verification lane ledger while retaining generic predicate execution; `tmp/fact-relocation/W02-P05-verification-ledger.md`.

### Phase `W02.P06` - lane 5 - typed legal and IVA decision tables

Owner: Luna/max agent 5. Track tmp/fact-relocation/W02-P06-legal-tables-ledger.md. Own ordered legal, IVA, activity, regime, category, and official-code rows. Reconcile existing IVA facts-registry work first; do not serialize arbitrary callables or invent generic maps. Complete when each table is canonical, relocated, retained as type metadata, or deferred to a schema ADR.

- [ ] `W02.P06.S36` - Relocate IVA classification rule identities ordering applicability and legal references; `src/cadrumo/domain/iva/classification.py and src/cadrumo/domain/iva/_classification_rules.py`.
- [ ] `W02.P06.S37` - Relocate IVA component expectations and typed component rows; `src/cadrumo/domain/iva/components.py and src/cadrumo/domain/iva/_component_rows.py`.
- [ ] `W02.P06.S38` - Relocate IVA deduction supply-nature and regime-legend tables; `src/cadrumo/domain/iva/deduction_facts.py and src/cadrumo/domain/iva/supply_nature.py and src/cadrumo/domain/iva/regime_legend.py`.
- [ ] `W02.P06.S39` - Relocate activity selector IRPF category and M210 income-code catalogues; `src/cadrumo/domain/transactions`.
- [ ] `W02.P06.S40` - Reconcile IVA catalogue and place-of-supply rows against active facts-registry work; `src/cadrumo/domain/iva/catalogue.py and src/cadrumo/domain/iva/place_of_supply.py`.
- [ ] `W02.P06.S41` - Classify OSS and IOSS declarations as governed facts or retained type metadata; `src/cadrumo/domain/iva/oss.py`.
- [ ] `W02.P06.S42` - Close the legal-table lane ledger or route missing typed shapes to a schema ADR; `tmp/fact-relocation/W02-P06-legal-tables-ledger.md`.

### Phase `W02.P07` - lane 6 - bridges retirement and negative gates

Owner: Luna/max agent 6. Track tmp/fact-relocation/W02-P07-bridges-retirement-ledger.md. Own generated bridges, duplicate-authority retirement, and extensions to existing negative gates. Do not author declarations owned by lanes 1-5. Complete when bridges derive from authority, every duplicate has a retirement condition, and reintroduction is mechanically blocked.

- [ ] `W02.P07.S43` - Generate or validate withholding foreign-asset and date-axis bridges from authority metadata; `src/cadrumo/domain/transactions/retencion_facts.py and src/cadrumo/application/_foreign_asset_thresholds.py and src/cadrumo/domain/modelos/modelo_fact_context.py`.
- [ ] `W02.P07.S44` - Confirm IVA rates and recargo modules contain only authority bridge mechanics; `src/cadrumo/domain/iva/rates.py and src/cadrumo/domain/iva/recargo_equivalencia.py`.
- [ ] `W02.P07.S45` - Generate or validate filing producer keys against registered export layouts; `src/cadrumo/core/filing_producer_key.py`.
- [ ] `W02.P07.S46` - Audit registry runtime constants and retain only generic evaluator and resolver mechanics; `src/cadrumo/domain/calculations/registry`.
- [ ] `W02.P07.S47` - Classify the M111 profile schedule without inferring legal ownership; `src/cadrumo/application/calculations/m111_no_retenciones.py`.
- [ ] `W02.P07.S48` - Extend the canonical facts retirement ledger with residual outcomes; `dev/registry/analysis/facts_external_constants_retirement.toml`.
- [ ] `W02.P07.S49` - Extend existing duplicate-import direct-read loader and provenance gates; `dev/quality and dev/registry/analysis`.
- [ ] `W02.P07.S50` - Close the bridge and retirement ledger after lanes one through five publish; `tmp/fact-relocation/W02-P07-bridges-retirement-ledger.md`.

## Wave `W03` - authority publication parity and closure

Integrate the six lane ledgers through the existing compiler and authority artifact, prove declaration and consumer parity, activate retirement gates, and close the campaign without introducing a new provider or runtime.

### Phase `W03.P08` - publish the integrated authority

Own integration and publication only. Complete when lane declarations have non-conflicting ownership, existing compilers accept them, the published artifact carries evidence and provenance, and runtime consumes that artifact without raw TOML fallback.

- [ ] `W03.P08.S51` - Merge the six lane ledgers and reject conflicting declaration ownership; `tmp/fact-relocation`.
- [ ] `W03.P08.S52` - Validate formula parameter applicability binding relation detail export and verification declarations; `src/cadrumo/_data/registry/aeat/modelos`.
- [ ] `W03.P08.S53` - Validate legal and IVA table declarations through existing typed fact families; `src/cadrumo/_data/registry/aeat/facts`.
- [ ] `W03.P08.S54` - Compile the integrated authoring tree through existing provider ownership; `dev/registry/compiler`.
- [ ] `W03.P08.S55` - Publish the authority artifact with digest evidence and provenance projection; `src/cadrumo/_data/registry/authority/authority.json`.
- [ ] `W03.P08.S56` - Resolve every relocated family through the published authority with explicit refusal behavior; `src/cadrumo/domain/calculations/registry/authority.py`.

### Phase `W03.P09` - prove lane and authority parity

Compare each lane against its prior Python declaration shape. Complete when all six ledgers carry parity evidence, consumers resolve through authority, and retained Python is demonstrably mechanics only.

- [ ] `W03.P09.S57` - Prove formula parameter and applicability parity; `tmp/fact-relocation/W02-P02-formulas-ledger.md`.
- [ ] `W03.P09.S58` - Prove binding relation projection and aggregation parity; `tmp/fact-relocation/W02-P03-bindings-ledger.md`.
- [ ] `W03.P09.S59` - Prove detail-record model-declaration and export-layout parity; `tmp/fact-relocation/W02-P04-detail-export-ledger.md`.
- [ ] `W03.P09.S60` - Prove verification reconciliation tolerance and refusal parity; `tmp/fact-relocation/W02-P05-verification-ledger.md`.
- [ ] `W03.P09.S61` - Prove typed legal and IVA table parity including absence semantics; `tmp/fact-relocation/W02-P06-legal-tables-ledger.md`.
- [ ] `W03.P09.S62` - Prove bridge derivation duplicate retirement and negative-gate parity; `tmp/fact-relocation/W02-P07-bridges-retirement-ledger.md`.
- [ ] `W03.P09.S63` - Prove integrated absence of parallel operative authority paths; `dev/registry/analysis`.

### Phase `W03.P10` - review and close the campaign

Perform final architectural review and persist closure. Complete when every relocation is published and consumed, every retained or deferred item has a reason, all negative gates are active, and no campaign-owned authority item remains unresolved.

- [ ] `W03.P10.S64` - Consolidate relocate retain bridge defer and unsupported outcomes; `tmp/fact-relocation/W03-closure-ledger.md`.
- [ ] `W03.P10.S65` - Run final registry compilation authority provenance and parity gates; `dev/registry/analysis`.
- [ ] `W03.P10.S66` - Run final duplicate-import direct-read loader and provenance negative gates; `dev/quality`.
- [ ] `W03.P10.S67` - Review the placement boundary and exclusions against the governing ADR; `.vault/adr/2026-09-09-facts-registry-governed-fact-catalogue-adr.md`.
- [ ] `W03.P10.S68` - Persist the campaign overview parity result and unresolved prerequisites; `tmp/fact-relocation/overview-report.md`.
- [ ] `W03.P10.S69` - Close the campaign only after every lane ledger and retirement condition is complete; `.vault/plan/2026-09-11-fact-relocation-plan.md`.

## Parallelization

W01 is a hard prerequisite. W02.P02 through W02.P07 are exactly six concurrent Luna/max lanes. Each lane has an exclusive declaration family, owner, ledger, and completion condition. Shared Python files are divided by named declaration responsibility; agents must coordinate before touching overlapping files and may not edit another lane's symbols. Lane 6 may prepare gates concurrently but cannot close retirement entries until lanes 1 through 5 publish their ledgers.

W03.P08 begins only after all six W02 ledgers and active facts-registry publication prerequisites are reconciled. W03.P09 depends on the published authority artifact. W03.P10 depends on parity evidence, negative gates, and closure-ledger review.

## Verification

- The W01 census accounts for all 654 broad candidates, 80 direct filename signals, and the grouped audit findings without treating filenames as dispositions.
- Every candidate has one owner and one relocate, retain, bridge, defer, or unsupported outcome with source locator, destination, dependency, and retirement condition.
- No completed or open facts-registry plan row is duplicated.
- Every relocated declaration is authored in an existing typed `_data` or TOML registry family and compiled by the existing provider path.
- The published authority artifact carries the declaration's digest, evidence, temporal coordinates, and provenance; runtime resolves it without raw TOML fallback.
- Each lane records parity evidence proving retained Python contains mechanics rather than a parallel filing-affecting declaration.
- Existing negative gates refuse duplicate constants, direct governed-directory reads, unregistered loaders, provenance-free results, and unresolved retirement entries.
- Missing evidence and unsupported schema shapes remain explicit; no lane substitutes zero, default, inferred applicability, generic dictionaries, or compatibility aliases.
- Final architectural review confirms the amended ADR boundary, and every Step and lane ledger is closed.
