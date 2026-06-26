---
tags:
  - '#plan'
  - '#binding-vocabulary-cli-cohesion'
date: '2026-06-26'
modified: '2026-06-26'
tier: L3
related:
  - '[[2026-06-26-binding-vocabulary-cli-cohesion-adr]]'
  - '[[2026-06-26-binding-vocabulary-cli-cohesion-reference]]'
---

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the
       related: field above.
     - The related: field carries the AUTHORISING documents
       (ADR, research, reference, prior plan) for every Step in
       this plan. Steps inherit this chain; per-row reference
       footers do not exist.
     - NEVER use [[wiki-links]] or markdown links in the
       document body. -->

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #plan) and one feature tag.
     Replace binding-vocabulary-cli-cohesion with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     tier is mandatory for new plans. Allowed: L1, L2, L3, L4.
     L1 = Steps only. L2 = Phases above Steps. L3 = Waves above
     Phases above Steps. L4 = Epic above Waves above Phases above
     Steps; PM association required. Pre-existing plans without this
     field default to L2.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'. The related field
     carries the AUTHORIZING documents (ADR, research, reference, prior
     plan) for every Step in this plan; Steps inherit this chain;
     per-row reference footers do not exist.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->


<!-- HIERARCHY AND TIERS:
     Epic > Wave > Phase > Step. Step is the canonical leaf-row
     noun. Execution Record artifact: <Step Record>.
     Tier is declared in frontmatter as tier: L1/L2/L3/L4
     (mandatory for new plans; pre-existing plans without the
     field default to L2 and the writer adds the field on first
     edit). The tier selects containers:
       L1 = Steps only.
       L2 = Phases above Steps.
       L3 = Waves above Phases above Steps.
       L4 = Epic above Waves above Phases above Steps; MUST declare
            a project-management association in the Epic intent
            block prose.
     Selection is by complexity criteria, not container counting.
     Writer never invents containers to qualify a tier. -->

<!-- IDENTIFIERS AND ROW CONTRACT:
     S##, P##, W## are flat, per-document, append-only, immutable.
     Promotion adds containers without renumbering. Gaps are not
     reused.
     Display paths are computed from current grouping:
       Step path:    L1 S##   L2 P##.S##   L3/L4 W##.P##.S##
       Phase heading:        L2 P##       L3/L4 W##.P##
       Wave heading:                      L3/L4 W##
     Row format:
       - [ ] `<display-path>` - imperative-verb action; `path/to/file`.
     Two-state checkboxes only ([ ] open, [x] closed). No per-row
     reference footers; wiki-links and markdown links are forbidden
     in plan body. Authorizing documents go in the plan's `related:`
     frontmatter once.
     ASCII spaced hyphens everywhere; em-dash (U+2014) and en-dash
     (U+2013) are forbidden. Step rows within a Phase are
     contiguous. -->

<!-- NO COMPRESSION:
     N self-similar actions = N rows. Never collapse into "for each
     X, do Y" / "across all callers, do Z" / "in every module,
     replace W". The rule applies at every tier including L1. -->

<!-- VAULTSPEC-CORE VAULT PLAN CLI:
     The `vaultspec-core vault plan` CLI is the canonical surface for
     structural manipulation of this plan document. Writers and
     executors MUST use `vaultspec-core vault plan step add/insert/move/
     remove/check/uncheck/toggle/edit`,
     `vaultspec-core vault plan phase add/move/remove/edit`,
     `vaultspec-core vault plan wave add/move/remove/edit`,
     `vaultspec-core vault plan epic intent`, and
     `vaultspec-core vault plan tier promote/demote` for every
     identifier-affecting change rather than hand-editing the row
     grammar. Hand edits are tolerated by the parser but flagged by
     `vaultspec-core vault plan check`; canonical-identifier preservation is
     guaranteed only when the CLI performs the mutation. Run
     `vaultspec-core vault plan --help` for the full subcommand
     surface. -->

# `binding-vocabulary-cli-cohesion` plan

Phase-2.4 (final) of the bindings-architecture-unification sweep: a behaviour-preserving rename / re-home pass that makes the bindings vocabulary load-bearing (F6 homonyms + false-friends), reconciles the forked source-pull CLI verb surface (F7), and carves the selector discriminated-union typing (F8) to a tracked deferred follow-up.

## Description

Phases 2.1-2.3 made the bindings engine cohesive in TYPE and STRUCTURE (one source-kind enum, one settled resolver contract / envelope, one fold-in / carry value layer); this final phase makes it cohesive in NAME, so a reader and a semantic search land on one vocabulary. The work is fenced to naming, CLI verb vocabulary, and the residual `selector` / `typed_enum` typing, and makes no semantic, type-value, or mechanism change.

Scope, grounded strictly in the phase-2.4 ADR (`2026-06-26-binding-vocabulary-cli-cohesion-adr`, findings F6 / F7 / F8) and the anchor reference (`2026-06-26-binding-vocabulary-cli-cohesion-reference`, anchor table A1-A4 / B1-B2 / C1-C3 / D1 / E1-E2 / F1-F3 / G1-G3 / H1-H3):

- W01 retires the four-way `BindingRow` homonym (A1 / A3 are real renames; A2 / A4 are role-distinct / module-private no-op asserts) and re-homes the two false-friend filenames out of the registry binding package (B1 the M232 CLI-row materialiser, B2 the BOE corpus verifier).
- W02 reconciles the three genuine `*SourceKind` homonyms as DISTINCT axes (C1 reconcile transport, C2 invoice direction with member strings preserved, C3 wallet-authority type alias) and disambiguates the OTHER `provider` role-family (D1) overloading the settled phase-2.2 resolver contract.
- W03 applies the domain-discriminating prefix discipline to the cross-tier `Observation` collisions only (E1 / E2) and asserts the three prefill tiers stay distinct (F1-F3).
- W04 reconciles the source-pull verb fork (F7 / G1-G3) under `aeat-cli-pull-and-file-standard`; operator-visible and locale-bound.
- W05 carries F8 (H1 / H2) as a DEFERRED follow-up per the ADR's explicit split permission.

The ADR-vs-HEAD drift corrections from the reference are applied: D1 re-points to `_source_mesh.py` / `_service.py` (the retired `_registry_provider.py` is gone, and the `ModeloSourceResolver` / `CalculationSourceResolution` / `merge_source_resolutions` contract is settled and NOT a rename target); C3 is treated as a `type` alias rename, not a class rename.

## Wave `W01` - BindingRow homonyms and false-friend re-homes

Retire the four-way BindingRow homonym into role-distinct names and re-home the two false-friend filenames that sit inside the registry binding package without being binding families. Pure rename / re-home, behaviour-preserving. Independent of later Waves; the renamed symbols are not consumed by W02-W04 rename targets. Backed by the phase-2.4 ADR (F6) and the reference anchor table A1-A4 and B1-B2.

### Phase `W01.P01` - Retire the BindingRow homonym into role-distinct names

Rename the two genuine BindingRow homonyms (A1 CLI list-row payload, A3 registry-query row) to role-distinct names; A2 and A4 are confirmed at HEAD as already role-distinct / module-private and handled as assert-only no-op checks.

- [x] `W01.P01.S01` - Rename BindingRowPayload to BindingListRowPayload as one atomic relocation:BindingRowPayload commit, sweeping the def, __all__, ModeloBindingsListResult.bindings, the _modelo_discovery_cli import, _binding_list_rows_for_report uses, and the test docstring; `regen docs-scaffold + locale + API-stub + docstring-core-struct deltas in the same commit; collect-only clean before commit; apply-cached own-only, abort-on-WIP; `src/aeat/entrypoints/cli/_modelo_payloads.py, src/aeat/entrypoints/cli/_modelo_discovery_cli.py, src/aeat/entrypoints/cli/tests/test_modelo_registry_surface.py`.
- [x] `W01.P01.S02` - Rename ModeloBindingRow to ModeloBindingQueryRow as one atomic relocation:ModeloBindingRow commit, sweeping the def, the rows tuple field, the _binding_rows builder, registry __all__, the registry package __init__ re-export, and the _schema.py docstring-core-struct xref; `regen docs-scaffold + locale + API-stub + docstring-core-struct in the same commit; collect-only clean before commit; apply-cached own-only, abort-on-WIP; `src/aeat/domain/calculations/registry/_queries.py, src/aeat/domain/calculations/registry/__init__.py, src/aeat/domain/calculations/registry/_schema.py`.
- [x] `W01.P01.S03` - Assert BindingPreviewRowPayload (A2) and _BindingRow (A4) are already role-distinct / module-private at HEAD and confirm no bare BindingRow stem collision remains; `rename _BindingRow to _EntradasBindingRow only if a residual stem collision is found in calc_sheets/_layout.py; `src/aeat/entrypoints/cli/_modelo_payloads.py, src/aeat/application/storage/calc_sheets/_layout.py`.
- [x] `W01.P01.S04` - Verify W01.P01 no-shift: run pytest --collect-only -q clean, the docstring-core-struct gate green, and the bindings-framework gate suite green; `assert pure-rename with no semantic / type-value change across the BindingRow renames; `src/aeat/domain/calculations/registry/tests, src/aeat/entrypoints/cli/tests/test_modelo_registry_surface.py`.

### Phase `W01.P02` - Re-home the two false-friend filenames out of the binding package

Re-home _m232_row_bindings.py (a CLI-row materialiser, not a binding family) and rename _sources.py (a BOE corpus verifier, unrelated to binding source kinds) so the binding / source names in the registry package are load-bearing, per binding-names-reserved-for-registry-input. Both are file relocations triggering API-stub regen in the same atomic commit.

- [x] `W01.P02.S05` - Re-home _m232_row_bindings.py to a row-materialisation module name dropping the _bindings stem (e.g. _m232_row_materialisation.py) toward the domain row-model surface as one atomic relocation:m232-row-materialisation commit; `update materialize_m232_related_party_rows and the single direct-submodule test import; run dev.docs.apidocs scaffold to regen the API-stub (remove the orphan, add the new stub) plus locale + docstring-core-struct in the same commit; collect-only clean before commit; apply-cached own-only, abort-on-WIP; `src/aeat/domain/calculations/registry/_m232_row_bindings.py, src/aeat/tests/test_storage_decimal_redaction_error_typing.py`.
- [x] `W01.P02.S06` - Rename _sources.py to a corpus-catalogue module name (e.g. _corpus_catalogue.py) as one atomic relocation:corpus-catalogue commit; `sweep verify_source_file / verify_source_catalogue at _validate.py, the registry package __init__ re-export and __all__, and the three test consumers; run dev.docs.apidocs scaffold to regen the API-stub plus locale + docstring-core-struct in the same commit; collect-only clean before commit; apply-cached own-only, abort-on-WIP; `src/aeat/domain/calculations/registry/_sources.py, src/aeat/domain/calculations/registry/_validate.py, src/aeat/domain/calculations/registry/__init__.py`.
- [x] `W01.P02.S07` - Verify W01.P02 no-shift: run pytest --collect-only -q clean, dev.docs.apidocs scaffold --check clean (no orphan / missing stubs), and the catalogue-verification / m232-row test consumers green; `assert the relocations changed only module paths and import sites, no behaviour; `src/aeat/domain/calculations/registry/tests/test_catalogue_verification.py, src/aeat/domain/calculations/registry/tests, docs/api`.

## Wave `W02` - SourceKind homonyms and the resolve / provider tangle

Reconcile the three genuine *SourceKind homonyms as DISTINCT axes (never folded into BindingSourceKind) and disambiguate the OTHER provider role-family that still overloads the settled phase-2.2 resolver contract. The ModeloSourceResolver / CalculationSourceResolution / merge_source_resolutions contract in _source_mesh.py is settled and is NOT a rename target. Pure rename, behaviour-preserving; C2 preserves member string values. Backed by the ADR (F6) and reference anchors C1-C3 and D1 (with the ADR-vs-HEAD drift correction re-pointing D1 to _source_mesh.py and _service.py).

### Phase `W02.P03` - Reconcile the three genuine SourceKind homonyms as distinct axes

Rename ModeloReconciliationSourceKind (reconcile transport / external-evidence kind), BusinessOperationInvoiceSourceKind (invoice direction; KEEP member string values), and the IvaCompensationAuthoritySourceKind type alias (wallet authority) to what each actually is. None are folded into BindingSourceKind.

- [x] `W02.P03.S08` - Rename ModeloReconciliationSourceKind to ModeloReconciliationEvidenceKind (reconcile transport / external-evidence axis, NOT folded into BindingSourceKind) as one atomic relocation:ModeloReconciliationSourceKind commit, sweeping all 30 occurrences across the reconcile CLI, the application modelo __init__ re-export, _reconcile.py, _justificante.py, and the two test modules; `regen docs-scaffold + locale + API-stub + docstring-core-struct in the same commit; collect-only clean before commit; apply-cached own-only, abort-on-WIP; `src/aeat/application/modelo/_reconcile.py, src/aeat/application/modelo/__init__.py, src/aeat/entrypoints/cli/_modelo_reconcile_cli.py, src/aeat/application/live/_justificante.py`.
- [x] `W02.P03.S09` - Rename the BusinessOperationInvoiceSourceKind TYPE to BusinessOperationInvoiceDirection (invoice-direction axis) KEEPING the payable_invoice / collectible_invoice member STRING values load-bearing per aeat-spanish-stem-naming, as one atomic relocation:BusinessOperationInvoiceSourceKind commit, sweeping all 31 occurrences across the ledger invoice CLI, the invoices _source_resolver, _business_operation_invoice.py, the ledger __init__ re-export, and the two test modules; `regen docs-scaffold + locale + API-stub + docstring-core-struct in the same commit; collect-only clean before commit; apply-cached own-only, abort-on-WIP; `src/aeat/application/ledger/_business_operation_invoice.py, src/aeat/application/ledger/__init__.py, src/aeat/entrypoints/cli/_ledger_business_invoice_cli.py, src/aeat/application/invoices/_source_resolver.py`.
- [x] `W02.P03.S10` - Rename the IvaCompensationAuthoritySourceKind type alias (Literal, not a class) to IvaCompensationAuthorityKind (wallet/compensation authority axis) as one atomic relocation:IvaCompensationAuthoritySourceKind commit, sweeping the def, the two field annotations, __all__, and the docs/conf.py nitpicky-resolver allowlist; `do NOT touch the legitimate M303 compensacion carve-out binding usages in the same module; regen docs-scaffold + API-stub + docstring-core-struct in the same commit; collect-only clean before commit; apply-cached own-only, abort-on-WIP; `src/aeat/domain/iva_compensation/_reconciliation.py, docs/conf.py`.
- [x] `W02.P03.S11` - Verify W02.P03 no-shift: run pytest --collect-only -q clean, the reconcile / ledger-invoice / iva-compensation test modules green, and assert the C2 member string values payable_invoice / collectible_invoice are unchanged; `confirm none of the three axes were folded into BindingSourceKind; `src/aeat/application/modelo/tests, src/aeat/application/ledger/tests, src/aeat/domain/iva_compensation`.

### Phase `W02.P04` - Disambiguate the provider role-family overloading the settled resolver contract

Rename the OTHER provider role-family (PerModeloAggregationProvider / PerModeloAggregationProviderContract, and the RegistrySchemaProvider / CasillaSchemaProvider schema-provider family) so a symbol's name says whether it is the port, the output, an aggregate, or a provider role. The phase-2.2 ModeloSourceResolver / CalculationSourceResolution / merge_source_resolutions contract is NOT renamed.

- [ ] `W02.P04.S12` - Rename the PerModeloAggregationProvider role-family to a name that says aggregation provider role (e.g. PerModeloAggregationContributor) for both PerModeloAggregationProvider and PerModeloAggregationProviderContract as one atomic relocation:PerModeloAggregationProvider commit, sweeping the enum, the contract model, the provider field / providers tuple, and the ~12 consumer sites; `do NOT rename ModeloSourceResolver / CalculationSourceResolution / merge_source_resolutions (settled by phase-2.2); regen docs-scaffold + locale + API-stub + docstring-core-struct in the same commit; collect-only clean before commit; apply-cached own-only, abort-on-WIP; `src/aeat/application/aggregation/_service.py, src/aeat/application/aggregation/_source_mesh.py`.
- [ ] `W02.P04.S13` - Rename the schema-provider role-family (RegistrySchemaProvider / CasillaSchemaProvider) to a name that says schema source / accessor distinct from the settled resolver port, as one atomic relocation:RegistrySchemaProvider commit, sweeping the class def, builder returns, __all__, and the ~6 consumer sites in filing runtime; `regen docs-scaffold + API-stub + docstring-core-struct in the same commit; collect-only clean before commit; apply-cached own-only, abort-on-WIP; `src/aeat/application/filing/runtime.py`.
- [ ] `W02.P04.S14` - Verify W02.P04 no-shift: run pytest --collect-only -q clean, the aggregation / filing-runtime test modules green, and assert ModeloSourceResolver / CalculationSourceResolution / merge_source_resolutions were NOT renamed (the phase-2.2 settled contract is intact); `src/aeat/application/aggregation/tests, src/aeat/application/filing/tests`.

## Wave `W03` - Observation prefix discipline and prefill disambiguation

Apply a domain-discriminating prefix to the bare Observation stem ONLY where it collides across tiers (calc / ledger-aggregation / live-capture / oracle), per the reference recommendation to scope this to cross-tier collisions rather than a full 30+ carrier per-tier sweep. Assert the three prefill modules (relation / previous-filing / AEAT borrador) are distinct without merging them. Pure rename / naming-clarity, behaviour-preserving. Backed by the ADR (F6) and reference anchors E1-E2 and F1-F3.

### Phase `W03.P05` - Prefix the cross-tier Observation collisions

Apply a domain-discriminating prefix to the bare *Observation data carriers in the ledger-aggregation, live-capture, and oracle tiers where the stem collides across tiers; the calc/registry tier (CasillaObservation et al.) is the anchor the others organise around and is not renamed. Role-suffixed names (*Requirement / *Repository / *Store / *Protocol) are out of scope.

- [ ] `W03.P05.S15` - Prefix the ledger-aggregation-tier Observation carriers with a consistent domain prefix (IvaLedgerObservation, OssIossLedgerObservation, RetencionObservation, CounterpartObservation, CounterpartAggregationObservation, ForeignAssetIngestObservation, RentaDeductibleExpenseObservation, the detail-record family RelatedPartyOperationObservation / Modelo720RowObservation / AtributionMemberObservation / RefundOperationObservation, WithholdingObservation, InvoiceObservation), one atomic relocation commit per renamed carrier tagged relocation:<symbol>, each regenerating docs-scaffold + API-stub + docstring-core-struct in the same commit; `collect-only clean before each commit; apply-cached own-only, abort-on-WIP; `src/aeat/domain/calculations/registry/_ledger_bindings.py, src/aeat/application/aggregation/_retenciones.py, src/aeat/application/aggregation/_counterpart.py, src/aeat/domain/calculations/registry/_counterpart_bindings.py, src/aeat/application/aggregation/_foreign_assets.py, src/aeat/domain/calculations/registry/_detail_record_bindings.py, src/aeat/domain/calculations/registry/_withholding_bindings.py, src/aeat/domain/calculations/registry/_invoice_bindings.py`.
- [ ] `W03.P05.S16` - Prefix the live-capture / sede-tier Observation carriers where the bare stem collides (FiledDeclaracionObservation, IvaCompensationWalletObservation, NifIvaCheckObservation, DeclaracionObservation, BorradorObservation), one atomic relocation commit per renamed carrier tagged relocation:<symbol>, each regenerating docs-scaffold + API-stub + docstring-core-struct in the same commit; `collect-only clean before each commit; apply-cached own-only, abort-on-WIP; `src/aeat/adapters/outbound/aeat/sede/_schema.py, src/aeat/adapters/outbound/aeat/sede/_nif_iva_check.py, src/aeat/adapters/inbound/declaracion/_schema.py, src/aeat/adapters/inbound/borrador/_schema.py`.
- [ ] `W03.P05.S17` - Prefix the oracle-tier Observation carriers where the bare stem collides (RentaWebOpenObservation, GroiObservation, AeatNifIvaObservation; `OracleModeloObservation stays as the oracle-marked calc-tier anchor), one atomic relocation commit per renamed carrier tagged relocation:<symbol>, each regenerating docs-scaffold + API-stub + docstring-core-struct in the same commit; collect-only clean before each commit; apply-cached own-only, abort-on-WIP; `src/aeat/domain/calculations/registry/_renta_web_open_oracle.py, src/aeat/domain/calculations/registry/_groi_oracle.py, src/aeat/domain/calculations/registry/_aeat_nif_iva_oracle.py`.
- [ ] `W03.P05.S18` - Verify W03.P05 no-shift: run pytest --collect-only -q clean, the affected aggregation / sede / oracle test modules green, and assert the calc/registry-tier anchor carriers (CasillaObservation, RegistryModeloObservation) and all role-suffixed *ObservationRequirement / *Repository / *Store / *Protocol names were NOT renamed; `src/aeat/application/aggregation/tests, src/aeat/domain/calculations/registry/tests`.

### Phase `W03.P06` - Assert the prefill-tier distinction without merging

Confirm and document that the three prefill modules name distinct tiers (relation prefill, previous-filing direct carry, AEAT borrador pre-fill) and are not merged; a naming-clarity assertion with low blast radius.

- [ ] `W03.P06.S19` - Assert and document the three prefill tiers are distinct and not merged: relation prefill (_relation_prefill.py, RelationPrefillSourceResolver), previous-filing direct carry (_binding_prefill.py), and AEAT borrador pre-fill (registry _schema.py aeat_prefilled / borrador-fed typed_enum); `add a clarifying module-docstring line on each where the distinction is not already explicit, one atomic commit; collect-only clean before commit; apply-cached own-only, abort-on-WIP; `src/aeat/application/calculations/_relation_prefill.py, src/aeat/application/calculations/_binding_prefill.py, src/aeat/domain/calculations/registry/_schema.py`.
- [ ] `W03.P06.S20` - Verify W03.P06 no-shift: run pytest --collect-only -q clean and assert the prefill modules retain distinct names and tiers with no merge and no behaviour change (docstring-only clarification); `src/aeat/application/calculations/tests`.

## Wave `W04` - CLI source-pull verb-fork reconciliation (operator-visible)

Reconcile the one produce-bound-casilla-values-from-sources intent that forked into three verbs (bindings preview / calc pull --compute / work calculate) into one learnable verb story under the aeat-cli-pull-and-file-standard discipline. OPERATOR-VISIBLE and LOCALE-BOUND: every verb rename sweeps the runtime write-policy allowlist, the error-registry default_suggestion fields, the cross-period next_action builders, the curated operator help, and the envelope command= identifiers, and is authored through the locale CLI. Gated by test_documented_command_conformance.py and test_json_schema_conformance.py. Backed by the ADR (F7) and reference anchors G1-G3.

### Phase `W04.P07` - Reconcile the source-pull verb surface and sweep operator-visible surfaces

Reconcile the three forked CLI verbs (bindings preview / calc pull --compute / work calculate) into one learnable verb story, authored through the locale CLI, with each rename sweeping the runtime write-policy allowlist, the error-registry suggestions, the cross-period next_action builders, the curated operator help, and the envelope command= identifiers. Gated by the documented-command and json-schema conformance suites.

- [ ] `W04.P07.S21` - OPERATOR-VISIBLE: rename the bindings preview verb (G1) to a value-bearing name that says what it sources rather than the UI gesture, under aeat-cli-pull-and-file-standard, as one atomic commit; `author the rename through the locale CLI (python -m aeat.locales modelo / set for cli.app.modelo.bindings.preview_help and list_help) and sweep the runtime write-policy allowlist, the error-registry default_suggestion fields, the cross-period next_action builders, the curated operator help, and the envelope command= identifiers; regen docs-scaffold + locale scaffold in the same commit; collect-only clean and test_documented_command_conformance + test_json_schema_conformance green before commit; apply-cached own-only, abort-on-WIP; `src/aeat/entrypoints/cli/_modelo_discovery_cli.py, src/aeat/application/storage_write_policy.py, src/aeat/core/errors/_registry.py, src/aeat/application/operator_surface/_help.py`.
- [ ] `W04.P07.S22` - OPERATOR-VISIBLE: reconcile the calc pull --compute verb (G2) with the one produce-bound-casilla-values-from-sources story, separating the Sheets-transport pull from the compute multiplexing per aeat-cli-pull-and-file-standard, as one atomic commit; `author through the locale CLI (cli.config.google.sync.calc.pull*) and sweep the runtime write-policy allowlist, error-registry default_suggestion, cross-period next_action builders, curated operator help, and envelope command= identifiers; regen docs-scaffold + locale scaffold in the same commit; collect-only clean and the two conformance gates green before commit; apply-cached own-only, abort-on-WIP; `src/aeat/entrypoints/cli/_config/_google_sync_calc.py, src/aeat/application/storage_write_policy.py, src/aeat/core/errors/_registry.py, src/aeat/application/operator_surface/_help.py`.
- [ ] `W04.P07.S23` - OPERATOR-VISIBLE: align the work calculate verb (G3, the canonical aggregation-engine entry) name to the reconciled one-verb story per aeat-cli-pull-and-file-standard, as one atomic commit; `author through the locale CLI (cli.app.modelo.work.calculate_help) and sweep the runtime write-policy allowlist, error-registry default_suggestion, cross-period next_action builders, curated operator help, and envelope command= identifiers; regen docs-scaffold + locale scaffold in the same commit; collect-only clean and the two conformance gates green before commit; apply-cached own-only, abort-on-WIP; `src/aeat/entrypoints/cli/_modelo_work_calculate_cli.py, src/aeat/application/storage_write_policy.py, src/aeat/core/errors/_registry.py, src/aeat/application/operator_surface/_help.py`.
- [ ] `W04.P07.S24` - Verify W04.P07 no-shift: run pytest --collect-only -q clean, test_documented_command_conformance.py and test_json_schema_conformance.py green, the locale parity + honesty gates green, and assert no dead operator instruction remains (write-policy allowlist, default_suggestion, next_action, operator help, and command= identifiers all reference the reconciled verb); `src/aeat/entrypoints/cli/tests/test_documented_command_conformance.py, src/aeat/entrypoints/cli/tests/test_json_schema_conformance.py, src/aeat/locales`.

## Wave `W05` - F8 selector discriminated-union typing (CARVED follow-up, deferred)

DEFERRED CARVE per the ADR and reference recommendation: typing DataBindingDefinition.selector as a discriminated union keyed by BindingSourceKind (per-family selector models BECOME the schema) is the largest residual and is split into its own tracked follow-up. This Wave is NOT a blocking dependency of W01-W04; it lands only if the W01-W04 rename pass lands light, otherwise it ships as a separate phase. Structured as a clean addition so the coordinator may later fold it in. Backed by the ADR (F8) and reference anchors H1-H2 (H3 is a clarifier, not in scope).

### Phase `W05.P08` - Type the binding selector as a discriminated union (deferred follow-up)

DEFERRED carve: replace the free-form DataBindingDefinition.selector Mapping with a discriminated union keyed by BindingSourceKind and narrow typed_enum to a typed enum-class reference. Not a blocking dependency of W01-W04; lands only if the rename pass is light or as a separate follow-up phase.

- [ ] `W05.P08.S25` - DEFERRED FOLLOW-UP (do NOT execute as part of W01-W04; `lands only if the rename pass is light or as a separate phase): replace the free-form DataBindingDefinition.selector BindingSelectorMap Mapping with a discriminated union keyed by BindingSourceKind so the per-family selector models in _bindings.py BECOME the schema rather than a validate-time overlay, updating the _schema.py field and alias, the _schema_scalars.py alias, and the _validate_binding_selector_shapes snapshot gate; atomic commit with docs-scaffold + API-stub + docstring-core-struct regen; collect-only clean before commit; apply-cached own-only, abort-on-WIP. NOTE: H3 source_revision_selector on the relation surface is NOT the binding selector and is out of scope; `src/aeat/domain/calculations/registry/_schema.py, src/aeat/domain/calculations/registry/_schema_scalars.py, src/aeat/domain/calculations/registry/_bindings.py`.
- [ ] `W05.P08.S26` - DEFERRED FOLLOW-UP (paired with the selector union): narrow the typed_enum stringly-typed pointer (str-or-None enum class name) on DataBindingDefinition to a typed enum-class reference, sweeping the bindings list CLI table, the ModeloBindingQueryRow projection, the borrador resolver, and the Sheets-pull router; `gated by test_schema_hygiene.py; atomic commit with docs-scaffold + API-stub + docstring-core-struct regen; collect-only clean before commit; apply-cached own-only, abort-on-WIP; `src/aeat/domain/calculations/registry/_schema.py, src/aeat/domain/calculations/registry/_queries.py`.
- [ ] `W05.P08.S27` - DEFERRED FOLLOW-UP verification: when F8 lands, run pytest --collect-only -q clean, test_schema_hygiene.py and the bindings-framework gate suite green, and assert the selector union is behaviour-preserving over the prior validate-time selector models; `if F8 is deferred to a separate phase, leave this Wave open and record the carve in the close note; `src/aeat/domain/calculations/registry/tests/test_schema_hygiene.py, src/aeat/domain/calculations/registry/tests`.

## Parallelization

Waves are sequenced by default, but the hard ordering here is weak because every Wave is a behaviour-preserving rename / re-home over a disjoint symbol set. The recommended order is W01 -> W02 -> W03 -> W04, with W05 (F8) deferred and unordered.

- W01 and W02 touch disjoint symbol families (BindingRow / false-friend files vs SourceKind / provider) and could run in parallel; sequence them only to keep the collect-only gate attributable per Wave in the shared worktree.
- Within W01, P01 (BindingRow renames) and P02 (false-friend re-homes) are independent and parallelizable.
- Within W02, P03 (SourceKind homonyms) and P04 (provider role-family) are independent and parallelizable; neither touches the settled `_source_mesh.py` resolver contract.
- Within W03, P05 (Observation prefix, three tier-group steps) and P06 (prefill assert) are independent; the three P05 steps (ledger-aggregation / live-capture / oracle tiers) are mutually independent and parallelizable, each its own atomic relocation commit.
- W04 (the operator-visible CLI verb reconciliation) is best landed after W01-W03 so the renamed payload / query-row symbols it references are already settled; its three verb steps (G1 / G2 / G3) share the operator-surface sweep files (`storage_write_policy.py`, `_registry.py`, `operator_surface/_help.py`) and so must be serialized within the Phase to avoid index contention.
- W05 (F8) is a DEFERRED follow-up: it is NOT a blocking dependency of W01-W04 and is unordered. The coordinator may fold it in as a final landing if W01-W04 land light, or split it to its own phase; the plan is structured so either is a clean addition.

Every Step is its own atomic explicit-path commit tagged `relocation:<symbol>` (or the verb-rename equivalent) with the docs-scaffold, locale regen, API-stub, and docstring-core-struct deltas in the SAME commit; `pytest --collect-only -q` is clean immediately before each commit. In this shared worktree each Step uses the apply-cached own-only drive and aborts on non-authored WIP in a scoped file.

## Verification

Mission success: a semantic search for any binding / source / carry / CLI concept returns one canonical answer, and the bindings vocabulary is load-bearing in name as well as type and structure. Per-Wave verification gates (one verification Step per Phase):

- Behaviour-preserving by construction: every Wave's verification Step asserts no-shift via `pytest --collect-only -q` clean, the conformance gates green, and the bindings-framework gate suite (the registry `test_binding_*` set, target 94 + 55 green) green. No semantic, type-value, or mechanism change in any Step.
- W01: collect-only clean, docstring-core-struct gate green, `dev.docs.apidocs scaffold --check` clean (no orphan / missing stubs after the B1 / B2 file relocations).
- W02: collect-only clean; the reconcile / ledger-invoice / iva-compensation and aggregation / filing-runtime test modules green; the C2 member strings (`payable_invoice` / `collectible_invoice`) unchanged; `ModeloSourceResolver` / `CalculationSourceResolution` / `merge_source_resolutions` NOT renamed.
- W03: collect-only clean; the affected aggregation / sede / oracle test modules green; the calc/registry-tier anchor carriers and all role-suffixed `*Observation*` names NOT renamed; the prefill modules retain distinct names and tiers.
- W04 (operator-visible): collect-only clean; `test_documented_command_conformance.py` and `test_json_schema_conformance.py` green; the locale parity + honesty gates green; no dead operator instruction remains across the write-policy allowlist, error-registry `default_suggestion`, cross-period `next_action` builders, curated operator help, and envelope `command=` identifiers.
- W05 (deferred): when F8 lands, collect-only clean, `test_schema_hygiene.py` and the bindings-framework gate suite green, and the selector union behaviour-preserving over the prior validate-time selector models. If deferred to a separate phase, this Wave stays open and the carve is recorded in the close note.

The plan is complete when every Step in W01-W04 is closed; W05 (F8) is permitted to remain open as the tracked deferred follow-up per the ADR's explicit split.
