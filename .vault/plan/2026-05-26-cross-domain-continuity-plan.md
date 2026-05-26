---
tags:
  - '#plan'
  - '#cross-domain-continuity'
date: '2026-05-26'
tier: L4
related:
  - '[[2026-05-26-cross-domain-continuity-audit]]'
  - '[[2026-05-26-cli-testimonial-audit]]'
  - '[[2026-05-21-cli-testimonial-audit]]'
  - '[[2026-05-26-corporate-tax-runtime-plan]]'
  - '[[2026-05-21-taxpayer-type-applicability-plan]]'
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

<!-- RETIRED: P02, S01 -->

# `cross-domain-continuity` `cross-domain continuity remediation epic - open-ended persona-driven correctness campaign` plan

## Epic intent

Drive the AEAT tool to verifiable cross-domain correctness across ledger, modelo, filing-record, overview and registry surfaces and across years and periods. Close the 20 root-cause clusters catalogued in the round-6 audit (Clusters A through T), backfill the systemic registry-data gaps, and put a single source of truth under every contract round-6 surfaced as drifted. Project-management association: this epic is owned by the round-6 testimonial campaign feedback loop; until an external PM board entry is registered the round-6 cross-domain-continuity audit at .vault/audit/2026-05-26-cross-domain-continuity-audit.md is the canonical campaign anchor. Timeline horizon open-ended: the campaign terminates only when a full persona-fleet pass surfaces zero BLOCKER and zero MAJOR findings AND a full Haiku drift sweep returns zero in-scope drift across the 1400-plus Python files.

## Wave `W01` - stabilisation: ledger CLI boundary, period unification, boolean canonical, i18n placeholder, CIF letters

Unblock every other Wave by removing the single most frequent operator-facing failure (the generic config repair loop on ledger list view update classify allocate split), unifying the four period-normalisation sites onto a single contract, aligning the boolean canonical string across wizard and binding layers, fixing the i18n placeholder silent-swallow, and consolidating the two CIF letter constants.

### Phase `W01.P01` - split the validation boundary into input versus stored-data variants

The generic command_error_boundary catches every pydantic ValidationError and emits the misleading config repair message. Split the boundary so a stored-data deserialisation failure surfaces a different message with a different remediation.

- [x] `W01.P01.S02` - add a typed StoredDataValidationBoundaryError class with distinct locale key and remediation suggestion; `src/aeat/entrypoints/cli/_errors.py`.
- [x] `W01.P01.S03` - register the new error class in the error code catalogue; `src/aeat/core/errors/registry/_application.py`.
- [x] `W01.P01.S04` - add four locale keys es en ca hu for the stored-data boundary via the locale CLI; `src/aeat/locales/`.
- [x] `W01.P01.S05` - wrap UserProfileRecord model_validate_json at the profile repository load boundary in a typed StoredProfileDriftError so drift surfaces as a domain error before reaching command_error_boundary; `src/aeat/application/user_profile/_repository.py`.
- [x] `W01.P01.S06` - narrow command_error_boundary to discriminate input-time versus load-time ValidationError; `src/aeat/entrypoints/cli/_errors.py`.
- [x] `W01.P01.S07` - real-CLI tests proving drifted stored profile gets stored-data message and malformed flag gets input message; `src/aeat/entrypoints/cli/test_errors_boundary.py`.

### Phase `W01.P03` - per-verb validation handlers on every ledger CLI verb

Two ledger verbs have local _ledger_validation_bad catches; five rely on the generic boundary and emit the misleading config repair message. Wire local handlers on all five.

- [x] `W01.P03.S08` - wrap _patch_from_options and update_manual_transaction_fields call inside ledger_update in a try/except ValidationError as exc: raise _ledger_validation_bad(exc) from exc mirroring the pattern already in ledger_classify; `surfaces field-combination errors as operator-readable refusals instead of the opaque boundary message; `src/aeat/entrypoints/cli/_ledger.py`.
- [x] `W01.P03.S09` - no code change required in ledger_list; `the Cluster A opaque-boundary symptom is resolved upstream by S05 stored-profile-drift guard; ledger_list has no ValidationError path of its own; record this as a documentation note in the verb and close the Step; `src/aeat/entrypoints/cli/_ledger.py`.
- [x] `W01.P03.S10` - no code change required in ledger_view; `same rationale as S09; ledger_view takes only a transaction-id string not a multi-field patch; record as documentation note and close; `src/aeat/entrypoints/cli/_ledger.py`.
- [x] `W01.P03.S11` - add _ledger_validation_bad catch to ledger_allocate; `src/aeat/entrypoints/cli/_ledger.py`.
- [x] `W01.P03.S12` - add _ledger_validation_bad catch to ledger_split; `src/aeat/entrypoints/cli/_ledger.py`.
- [x] `W01.P03.S13` - real-CLI tests asserting each ledger verb surfaces specific field error not generic boundary; `src/aeat/entrypoints/cli/test_ledger_validation_paths.py`.

### Phase `W01.P04` - confirmable classification patch no-op semantics

_command_from_patch zeroes classification-adjacent fields when classification is BUSINESS; if the stored record is already BUSINESS the patch is field-identical and the mutation guard fires. Provide a confirmable path.

- [x] `W01.P04.S14` - guard the no-op mutation-signature so re-affirming the same business_classification on an already-classified transaction does not raise; `treat field-for-field-identical commands as a confirmed no-op instead of an error; `src/aeat/application/ledger/_actions.py`.
- [x] `W01.P04.S15` - add --reaffirm flag on ledger classify bypassing the no-op guard for explicit re-application; `src/aeat/entrypoints/cli/_ledger.py`.
- [x] `W01.P04.S16` - unit tests covering patch-without-zeroing reaffirm semantics and field-by-field no-op surfacing; `src/aeat/application/ledger/test_actions.py`.

### Phase `W01.P05` - boolean canonical contract unification

Wizard persistence emits lowercase true and false; binding-side Decimal coercion expects Python-style True and False. Adopt wizard canonical as project single boolean string form.

- [x] `W01.P05.S17` - update _decimal_value to accept lowercase canonical strings in addition to the Python form; `src/aeat/application/modelo/_profile_binding.py`.
- [x] `W01.P05.S18` - promote lowercase boolean tokens to Python bool in _coerce_profile_fact_value so union resolves before coercion; `src/aeat/domain/user_profile/_values.py`.
- [x] `W01.P05.S19` - preserve typed ProfileFactValue through _profile_fact_index instead of stringifying at the index entry; `update _resolve_one and _decimal_value to accept object and route via isinstance(value, bool) before Decimal parse; engine-facing ProfileSourcedBindingResult fields unchanged; add guard at enum routing site to reject bool-typed values as enum dispatch keys; `src/aeat/application/modelo/_profile_binding.py`.
- [x] `W01.P05.S20` - regression test exercising full wizard to persistence to binding to decimal_value path for boolean profile fact; `src/aeat/application/modelo/test_profile_binding_real_path.py`.
- [x] `W01.P05.S21` - project-wide grep for any other site checking Python True or False as a sentinel and convert each to the lowercase canonical; `src/aeat/`.

### Phase `W01.P06` - CIF identity validator consolidation

Two parallel CIF validators disagree on whether K is a valid leading letter. Unify to a single canonical constant in a single module.

- [x] `W01.P06.S22` - add a module-level cross-reference comment in _tax_id.py documenting that _CIF_LEADERS is a historical-tolerance superset of _documents._CIF_KIND_LETTERS K L M accepted only on the legacy NIF validator path not the IdentityDocument shape gate; `src/aeat/core/identity/_tax_id.py`.
- [x] `W01.P06.S23` - add a paired comment at _CIF_KIND_LETTERS in _documents.py explaining the 17-char set is the AEAT current-spec closed catalogue and K L M are deliberately excluded as historical-only forms tolerated by the legacy path; `src/aeat/core/identity/_documents.py`.
- [x] `W01.P06.S24` - pin the intentional split with a regression test asserting K L M are not in _CIF_KIND_LETTERS while validate_spanish_tax_id still accepts a K-led valid CIF; `prevents future consolidation from silently collapsing the two sets; `src/aeat/core/identity/test_documents.py`.

### Phase `W01.P07` - period normalisation unification

Four separate period-resolution sites: parse_canonical_period period_start_date period_end_date in domain; workflow_period_for_work_unit in application modelo; _registry_period_token in workflow engine. The 1P 2P 3P addition reached only two of three siblings; verify breaks.

- [x] `W01.P07.S25` - add 1P 2P 3P arms to parse_canonical_period; `src/aeat/domain/period.py`.
- [x] `W01.P07.S26` - consolidate workflow_period_for_work_unit to call parse_canonical_period; `src/aeat/application/modelo/_actions.py`.
- [x] `W01.P07.S27` - consolidate _registry_period_token to share a normaliser with the calculate path; `src/aeat/application/workflow/_engine.py`.
- [x] `W01.P07.S28` - property test that for every supported period token all three sibling functions agree; `src/aeat/domain/test_period_property.py`.
- [x] `W01.P07.S29` - regression test that modelo work verify succeeds on the same 1P token create and calculate accepted; `src/aeat/entrypoints/cli/test_modelo_period_consistency.py`.

### Phase `W01.P08` - i18n placeholder validator silent-swallow elimination

_interpolate swallows KeyError on placeholder context mismatches and emits half-rendered text. Fix the immediate bracket_no_window mismatch and add an i18n-stack validation step.

- [x] `W01.P08.S30` - rename context key filing_date to as_of at the bracket_no_window raise site; `src/aeat/domain/calculations/registry/_formula_runtime.py`.
- [x] `W01.P08.S31` - strengthen _interpolate to emit developer-visible warning on unmatched placeholders; `src/aeat/core/i18n/_render.py`.
- [x] `W01.P08.S32` - add project-wide i18n placeholder parity validator over every tr call site; `src/aeat/core/i18n/test_placeholder_parity.py`.

### Phase `W01.P09` - Wave-1 review and persona re-run and plan expansion BREAKPOINT

Mandated breakpoint. Dispatch code-reviewer on Wave-1 commits, round-7 persona fleet, fresh Haiku drift sweep on touched files, consolidate findings audit, EXPAND this plan in place with every new BLOCKER MAJOR.

- [ ] `W01.P09.S33` - dispatch vaultspec-code-reviewer against every Wave-1 commit and consolidate verdict; `.vault/exec/`.
- [ ] `W01.P09.S34` - dispatch round-7 persona fleet minimum five distinct tax shapes including one round-6 repeat; `.vault/audit/`.
- [x] `W01.P09.S35` - dispatch fresh Haiku drift sweep over Wave-1 touched files to confirm no new drift; `src/aeat/`.
- [ ] `W01.P09.S36` - consolidate round-7 findings into a new audit document via vaultspec CLI; `.vault/audit/`.
- [ ] `W01.P09.S37` - expand this plan in place: every new BLOCKER and MAJOR becomes a new Phase or Step in the appropriate Wave; `re-run vault plan check; `.vault/plan/2026-05-26-cross-domain-continuity-plan.md`.

## Wave `W02` - applicability and calendar consolidation

Single source of truth for does Modelo X apply to this profile. Today three sources exist: the seed table in application overview _applicability.py, the canonical superset in domain calculations registry _applicability.py, and per-window applicability_conditions in registry TOMLs. W02 collapses them to one.

### Phase `W02.P10` - canonicalise _MODELO_APPLICABILITY_RULES

The domain version is the superset (179 lines more; carries Modelo202Modality system, iter_modelo_applicability_rules, taxpayer_model_is_declared). The application version is the stale copy. Collapse.

- [x] `W02.P10.S38` - delete duplicate _MODELO_APPLICABILITY_RULES and derive_modelo_applicability from application copy; `replace with thin re-export from domain module; `src/aeat/application/overview/_applicability.py`.
- [x] `W02.P10.S39` - delete duplicate reason constants _INCOMPLETE_LEGAL_REFS _ATTRIBUTION_PASS_THROUGH_LEGAL_REFS _ATTRIBUTION_PASS_THROUGH_REASON _INCOMPLETE_UNDECLARED_REASON _INCOMPLETE_UNRULED_REASON _INCOMPLETE_UNDETERMINED_REASON; `src/aeat/application/overview/_applicability.py`.
- [x] `W02.P10.S40` - update CLI consumer to import from canonical domain module or via thin application re-export; `src/aeat/entrypoints/cli/_modelo.py`.
- [x] `W02.P10.S41` - remove private-symbol entries from applicability facade __all__; `private symbols must not be in __all__; `src/aeat/domain/calculations/registry/applicability.py`.
- [x] `W02.P10.S42` - regression test asserting _MODELO_APPLICABILITY_RULES is a unique source with one definition and one identity; `src/aeat/domain/calculations/registry/test_applicability_canonical.py`.

### Phase `W02.P11` - calendar to deadline-engine unification

Two parallel mechanisms decide applicability (Python seed table plus per-window TOML applicability_conditions). Calendar drops non-APPLICABLE silently. _GATING_FIELDS is hardcoded.

- [ ] `W02.P11.S43` - confirm _MODELO_APPLICABILITY_RULES is the canonical modelo-level applicability authority; `add module docstring documenting that modelo-level rules live in Python while window-level applicability_conditions live on ModeloDeadlineWindow registry slot; audit the 18 modelos to ensure every rule populates applicable_entity_types required_income_categories required_estimation_regimes and required_payer_fact where the modelo demands those axes; `src/aeat/domain/calculations/registry/_applicability.py`.
- [ ] `W02.P11.S44` - replace the hardcoded 5-entry _GATING_FIELDS dict with a derivation from _MODELO_APPLICABILITY_RULES; `for each rule emit profile_key modelos message_key fix_command tuples covering income-categories entity-types estimation-regimes payer-facts; the resulting projection must be a function not a dict so it stays in sync as rules evolve; `src/aeat/application/overview/__init__.py`.
- [ ] `W02.P11.S45` - add calendar-side diagnostic surface --show-suppressed surfacing every obligation the calendar dropped and the verdict reason; `src/aeat/application/overview/__init__.py`.
- [ ] `W02.P11.S46` - regression test asserting build_overview_explain and build_overview_calendar produce identical ApplicabilityVerdict per modelo for the same profile; `pin the current correct agreement state to prevent future drift; `src/aeat/application/overview/test_calendar_applicability_consistency.py`.

### Phase `W02.P12` - Modelo 202 modality gate wiring Cluster Q

derive_modelo_202_modality is orphaned in the domain. Casillas 03 and 32 compute unconditionally. INCN is not a registry binding for Modelo 202.

- [ ] `W02.P12.S47` - add an INCN profile binding to the Modelo 202 2025-y-siguientes revision; `src/aeat/_data/registry/aeat/modelos/202/revisions/2025-y-siguientes/bindings/`.
- [ ] `W02.P12.S48` - add the modality gate as a registry-level applicability condition on casillas 03 and 32; `src/aeat/_data/registry/aeat/modelos/202/revisions/2025-y-siguientes/casillas/`.
- [ ] `W02.P12.S49` - wire derive_modelo_202_modality into registry formula composition as a guard predicate OR remove the orphan function; `src/aeat/domain/calculations/registry/_applicability.py`.
- [ ] `W02.P12.S50` - end-to-end CLI test: SL with INCN above 6.000.000 EUR gets only Art. 40.3; `below threshold both modalities reachable; `src/aeat/entrypoints/cli/test_modelo_202_modality.py`.

### Phase `W02.P13` - Wave-2 review and persona re-run and plan expansion BREAKPOINT

Mandated breakpoint. Dispatch code-reviewer, round-8 persona fleet focused on cross-domain applicability, Sonnet grounding on calendar to applicability join, consolidate findings, expand plan in place.

- [ ] `W02.P13.S51` - dispatch vaultspec-code-reviewer against every Wave-2 commit; `.vault/exec/`.
- [ ] `W02.P13.S52` - dispatch round-8 persona fleet (landlord autonomo SL gestor multi-profile) CLI only; `.vault/audit/`.
- [ ] `W02.P13.S53` - dispatch Sonnet grounding pass against calendar to applicability join to confirm unification holds; `src/aeat/application/overview/`.
- [ ] `W02.P13.S54` - consolidate round-8 findings into new audit document via vaultspec CLI and expand this plan in place; `.vault/audit/`.

## Wave `W03` - corporate-tax-runtime hardening

The corporate-tax-runtime plan 8 of 8 Steps complete claim was premature: Clusters D Q R S T are real regressions visible to a real SL operator. Wave 3 closes them.

### Phase `W03.P14` - pyme bracket_table temporal coverage Cluster R

is.modelo-200.tipo-gravamen-pyme brackets cover 2025+ only inside a revision named 2024-y-siguientes. Resolve.

- [ ] `W03.P14.S55` - decide and document either backfill 2024 pyme brackets at LIS Art. 29 2024 rate OR revise the revision identity so 2024 routes elsewhere; `.vault/exec/`.
- [ ] `W03.P14.S56` - apply the chosen fix to the parameter; `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/records/parameters.toml`.
- [ ] `W03.P14.S57` - add registry-validation check that every bracket_table parameter brackets cover the revision declared date range; `src/aeat/domain/calculations/registry/_validate_revision_rules.py`.
- [ ] `W03.P14.S58` - regression test: Modelo 200 work unit with 2024 filing_period and micro-empresa profile calculates without bracket_no_window; `src/aeat/domain/calculations/registry/test_modelo_200_temporal_coverage.py`.

### Phase `W03.P15` - Modelo 200 base imponible input casilla resolution Cluster D.3

Casilla 552 IS manually inputable; the CLI accepts bare numeric 552 but the registry needs DP200014:00552. Normalise.

- [ ] `W03.P15.S59` - add CLI normalisation step on --casilla values that resolves bare numeric tokens to qualified PREFIX:NNNNN keys; `src/aeat/entrypoints/cli/_modelo.py`.
- [ ] `W03.P15.S60` - improve the unknown casilla error message to suggest the qualified form when bare numeric provided; `src/aeat/entrypoints/cli/_modelo.py`.
- [ ] `W03.P15.S61` - regression test asserting --casilla 552=85000 is accepted and routes to DP200014:00552; `src/aeat/entrypoints/cli/test_modelo_casilla_normalisation.py`.

### Phase `W03.P16` - profile-fact resolution audit Cluster T

Every renta-2025-profile-* binding shows missing despite the fact existing on the profile. Audit the selector projection chain.

- [ ] `W03.P16.S62` - for every renta-2025-profile-* binding list selector.field value and verify against canonical profile-fact path wizard emits; `src/aeat/_data/registry/aeat/modelos/100/revisions/2025/bindings/`.
- [ ] `W03.P16.S63` - repeat for every renta-2024-profile-* modelo-200-2024-profile-* modelo-303-*-profile-* binding; `src/aeat/_data/registry/aeat/modelos/`.
- [ ] `W03.P16.S64` - identify the mismatch class key-namespace missing projection arm schema-version drift; `apply canonical fix at correct boundary; `src/aeat/application/modelo/_profile_binding.py`.
- [ ] `W03.P16.S65` - regression test constructing realistic profile and asserting every renta-2025-profile-* binding resolves to stored fact; `src/aeat/application/modelo/test_profile_binding_real_path.py`.

### Phase `W03.P17` - end-to-end CLI test coverage through real profile to binding path

Corporate-tax-runtime test suite bypassed _profile_binding.py by passing Decimal values directly. Add real-CLI coverage so this regression class cannot recur.

- [ ] `W03.P17.S66` - for every Modelo 200 202 303 130 100 calculation lane add CLI-level test that creates a profile via aeat config profile create flows through wizard persistence and runs calculation asserting cuota matches external oracle; `src/aeat/entrypoints/cli/test_modelo_calculation_through_real_cli.py`.
- [ ] `W03.P17.S67` - backfill external oracles for cuota assertions: AEAT Manual de Sociedades Modelo 200, AEAT folleto Modelo 130, AEAT Manual de IVA Modelo 303, AEAT Manual de Renta Modelo 100; `src/aeat/entrypoints/cli/test_modelo_calculation_through_real_cli.py`.

### Phase `W03.P18` - Wave-3 review and persona re-run and plan expansion BREAKPOINT

Mandated breakpoint. Code-reviewer, repeat Joan SL persona plus fresh sociedad-anonima, repeat Pere pensioner-landlord, consolidate findings, expand plan in place.

- [ ] `W03.P18.S68` - dispatch vaultspec-code-reviewer against every Wave-3 commit; `.vault/exec/`.
- [ ] `W03.P18.S69` - re-run round-6 Joan SL persona to confirm every B-JOAN-* finding closed; `plus fresh sociedad-anonima persona; `.vault/audit/`.
- [ ] `W03.P18.S70` - re-run round-6 Pere pensioner-landlord to confirm Cluster T closed and the IRPF tarifa is applied; `.vault/audit/`.
- [ ] `W03.P18.S71` - consolidate findings and expand this plan in place; `.vault/plan/2026-05-26-cross-domain-continuity-plan.md`.

## Wave `W04` - verification semantics

verify rubber-stamps substantively empty drafts because every casilla in Modelo 130 is required false. Extend the verify contract to include substantive predicates.

### Phase `W04.P19` - substantive verification predicates

Decide and implement substantive predicates on the registry side so empty drafts no longer trivially pass verification.

- [ ] `W04.P19.S72` - decide and document whether registry marks currently-optional casillas as required true OR a separate verification_predicates field is introduced; `.vault/exec/`.
- [ ] `W04.P19.S73` - apply the chosen approach to Modelo 130 first; `src/aeat/_data/registry/aeat/modelos/130.toml`.
- [ ] `W04.P19.S74` - apply the same approach to Modelo 100 303 200 202; `src/aeat/_data/registry/aeat/modelos/`.
- [ ] `W04.P19.S75` - extend _required_input_casillas_for_revision and _classify_verification_outcome to honour substantive predicates; `src/aeat/application/modelo/_actions.py`.
- [ ] `W04.P19.S76` - regression test that Modelo 130 with all casillas zero is no longer verificado_completo; `src/aeat/application/modelo/test_verification_substance.py`.

### Phase `W04.P20` - verification path naming and boundary documentation

Two verify paths exist work-unit gate and PDF cross-check. Document the boundary.

- [ ] `W04.P20.S77` - add architectural docstring at modelo init and verification init explaining the boundary; `consider renaming verify_modelo_revision to validate_modelo_revision; `src/aeat/application/`.

### Phase `W04.P21` - Wave-4 review and persona re-run BREAKPOINT

Mandated breakpoint. Code-reviewer and persona-fleet re-run focused on verify path.

- [ ] `W04.P21.S78` - dispatch vaultspec-code-reviewer against every Wave-4 commit; `.vault/exec/`.
- [ ] `W04.P21.S79` - re-run Marc autonomo IT and fresh persona reaching work verify confirm verificado_completo refused on empty drafts; `.vault/audit/`.
- [ ] `W04.P21.S80` - consolidate findings and expand this plan in place; `.vault/plan/2026-05-26-cross-domain-continuity-plan.md`.

## Wave `W05` - ledger surface completion

Modelo 130 income side has no ledger aggregation resolver. Non-EUR transactions silently drop. No bulk classify. No IVA-wallet inspector. No classification enums for intracom export suffered retention.

### Phase `W05.P22` - Modelo 130 income-side aggregation resolver

Add the missing LedgerRentaIncomeAggregationSourceResolver and wire it into Modelo 130.

- [ ] `W05.P22.S81` - add LedgerRentaIncomeAggregationSourceResolver covering IRPF actividad-economica income side; `src/aeat/application/aggregation/_modelo_bindings.py`.
- [ ] `W05.P22.S82` - implement income-side aggregation logic following the expense-side resolver pattern; `src/aeat/application/aggregation/_renta_income_ledger.py`.
- [ ] `W05.P22.S83` - register binding modelo-130-actividad-economica-ingresos-cumulative consuming the new resolver; `src/aeat/_data/registry/aeat/modelos/130.toml`.
- [ ] `W05.P22.S84` - bind Modelo 130 casilla 01 to the new aggregation result; `src/aeat/_data/registry/aeat/modelos/130.toml`.
- [ ] `W05.P22.S85` - regression test real autonomo ledger imports flow into Modelo 130 casilla 01 with expected cumulative ingresos; `src/aeat/application/aggregation/test_renta_income_aggregation.py`.

### Phase `W05.P23` - FX-conversion contract for non-EUR transactions

_iva_ledger.py and _renta_ledger.py silently drop non-EUR. Adopt single FX-conversion contract.

- [ ] `W05.P23.S86` - decide and document FX conversion strategy; `.vault/exec/`.
- [ ] `W05.P23.S87` - add fx_rate and value_in_eur fields on Transaction or aggregation row; `src/aeat/domain/transactions/_raw_transaction.py`.
- [ ] `W05.P23.S88` - implement chosen FX strategy in import path or aggregation layer; `src/aeat/adapters/inbound/financial/providers/_csv.py`.
- [ ] `W05.P23.S89` - replace duplicated currency-not-EUR guards with shared predicate; `src/aeat/application/aggregation/`.
- [ ] `W05.P23.S90` - regression test USD invoice imports with FX rate and aggregates with expected EUR value; `src/aeat/application/aggregation/test_fx_conversion.py`.

### Phase `W05.P24` - classification enums for intracom export and suffered retention

ledger classify accepts BUSINESS PERSONAL MIXED but no enums for entrega intracom export non-EU or ingreso con retencion suffered.

- [ ] `W05.P24.S91` - extend BusinessClassification with intracom-supply intracom-acquisition export-non-EU retained-income variants; `src/aeat/domain/transactions/_models.py`.
- [ ] `W05.P24.S92` - add counterparty_country field on Transaction currently only on Invoice; `src/aeat/domain/transactions/_models.py`.
- [ ] `W05.P24.S93` - extend ledger classify CLI to accept new axes; `src/aeat/entrypoints/cli/_ledger.py`.
- [ ] `W05.P24.S94` - wire new axes into IVA aggregation so Modelo 303 boxes 59 60 62 receive their bases; `src/aeat/application/aggregation/_iva_ledger.py`.
- [ ] `W05.P24.S95` - regression test autonomo with EU sales has box 59 populated correctly; `src/aeat/application/aggregation/test_intracom_export.py`.

### Phase `W05.P25` - bulk classify CSV-driven and rule-engine

Single-id classify unusable for hundreds of movements. Add bulk path.

- [ ] `W05.P25.S96` - implement ledger classify --from-csv flag accepting CSV with id classification category rows; `src/aeat/entrypoints/cli/_ledger.py`.
- [ ] `W05.P25.S97` - implement rule-based classifier surface ledger rule add description-pattern classification BUSINESS; `src/aeat/entrypoints/cli/_ledger.py`.
- [ ] `W05.P25.S98` - regression tests for bulk and rule paths; `src/aeat/entrypoints/cli/test_ledger_bulk_classify.py`.

### Phase `W05.P26` - IVA-wallet inspector verb

compensacion-pendiente-anteriores binding consumes previous-filing value but no operator-visible verb queries wallet balance.

- [ ] `W05.P26.S99` - add aeat app modelo iva-wallet balance verb surfacing current wallet balance contributing quarters and next pull date; `src/aeat/entrypoints/cli/_modelo.py`.
- [ ] `W05.P26.S100` - regression test verb returns coherent state after sequence of quarterly filings with credit; `src/aeat/entrypoints/cli/test_iva_wallet_inspector.py`.

### Phase `W05.P27` - Wave-5 review and persona re-run BREAKPOINT

Mandated breakpoint. Code-reviewer and repeat Laia Marc Joan to confirm ledger surface usable end-to-end.

- [ ] `W05.P27.S101` - dispatch vaultspec-code-reviewer against every Wave-5 commit; `.vault/exec/`.
- [ ] `W05.P27.S102` - re-run Laia e-commerce OSS UK Marc autonomo intracom and Joan SL intracom confirming OSS 349 UK IVA-wallet handled; `.vault/audit/`.
- [ ] `W05.P27.S103` - consolidate findings and expand this plan in place; `.vault/plan/2026-05-26-cross-domain-continuity-plan.md`.

## Wave `W06` - profile portability

Profile export ships identity only Cluster E. Import mints fresh UUIDs Cluster F.

### Phase `W06.P28` - full-bundle export schema

Design and implement a bundled-export schema that carries work units calculation revisions ledger entries and filing records with explicit confidentiality treatment for encrypted material.

- [ ] `W06.P28.S104` - design bundled-export schema with explicit confidentiality treatment for encrypted material; `src/aeat/domain/user_profile/_values.py`.
- [ ] `W06.P28.S105` - implement bundled serializer with schema-version bumping; `src/aeat/application/user_profile/`.
- [ ] `W06.P28.S106` - implement bundled deserializer with provenance preservation; `src/aeat/application/user_profile/`.
- [ ] `W06.P28.S107` - real-CLI roundtrip test export non-trivial profile and re-import to fresh storage root every artefact survives; `src/aeat/entrypoints/cli/test_profile_export_roundtrip.py`.

### Phase `W06.P29` - idempotent import

Add an idempotency mode that respects the bundle profile_id when no local profile of that id exists.

- [ ] `W06.P29.S108` - add idempotency mode that respects bundle profile_id when no local profile of that id exists and refuses or upserts when one does; `src/aeat/entrypoints/cli/_config/__init__.py`.
- [ ] `W06.P29.S109` - regression test re-importing same bundle twice produces one profile not two; `src/aeat/entrypoints/cli/test_profile_import_idempotency.py`.

### Phase `W06.P30` - Wave-6 review and persona re-run BREAKPOINT

Code-reviewer and Nuria gestor multi-profile re-run to confirm bundle now carries work ledger revisions filings.

- [ ] `W06.P30.S110` - dispatch vaultspec-code-reviewer against every Wave-6 commit; `.vault/exec/`.
- [ ] `W06.P30.S111` - re-run Nuria gestor multi-profile to confirm bundle now carries work and ledger and revisions and filings; `colleague-handover workflow viable; `.vault/audit/`.
- [ ] `W06.P30.S112` - consolidate findings and expand this plan in place; `.vault/plan/2026-05-26-cross-domain-continuity-plan.md`.

## Wave `W07` - IRPF tarifa and cross-period surfaces

Pere Modelo 100 returns 0 cuota the IRPF tarifa is not applied. 130 to 100 projection invisible. IVA-wallet not surfaced. Cross-fiscal-year compare verb absent.

### Phase `W07.P31` - IRPF tarifa wiring Cluster P

Trace Modelo 100 cuota path end-to-end for a pensioner-landlord profile and identify where the tarifa is silently zeroed.

- [ ] `W07.P31.S113` - trace Modelo 100 cuota path end-to-end for pensioner-landlord and identify where tarifa is silently zeroed; `.vault/exec/`.
- [ ] `W07.P31.S114` - confirm root cause class CCAA fact missing or wrong; `profile-fact bindings missing per Cluster T; rate lookup gated on wrong predicate; apply fix at correct boundary; `src/aeat/_data/registry/aeat/modelos/100/`.
- [ ] `W07.P31.S115` - regression test Pere profile base 35400 minimo 5550 Catalonia returns Modelo 100 cuota in expected range; `src/aeat/domain/calculations/registry/test_modelo_100_tarifa_real.py`.

### Phase `W07.P32` - 130 to 100 projection verb

The binding renta-2025-modelo-130-pagos-fraccionados exists; the projection is invisible from the operator surface.

- [ ] `W07.P32.S116` - add aeat app modelo project --target 100 --from 130-revisions verb surfacing projected year-end Modelo 100 from quarterly 130 filings; `src/aeat/entrypoints/cli/_modelo.py`.
- [ ] `W07.P32.S117` - regression test series of four filed 130 quarters produces sensible Modelo 100 projection; `src/aeat/entrypoints/cli/test_modelo_projection.py`.

### Phase `W07.P33` - cross-fiscal-year compare verb

Add an aeat app modelo compare verb surfacing prior-period versus current-period casilla deltas.

- [ ] `W07.P33.S118` - add aeat app modelo compare --year 2024 --year 2025 --modelo 100 verb surfacing prior-period versus current-period casilla deltas; `src/aeat/entrypoints/cli/_modelo.py`.
- [ ] `W07.P33.S119` - regression test against two fiscal years; `src/aeat/entrypoints/cli/test_modelo_compare.py`.

### Phase `W07.P34` - Wave-7 review and persona re-run BREAKPOINT

Code-reviewer and Pere Marc re-run confirming IRPF tarifa applied, 130 to 100 projection discoverable, IVA-wallet queryable.

- [ ] `W07.P34.S120` - dispatch vaultspec-code-reviewer against every Wave-7 commit; `.vault/exec/`.
- [ ] `W07.P34.S121` - re-run Pere pensioner-landlord and Marc autonomo to confirm tarifa applied 130-to-100 projection discoverable IVA-wallet queryable Pere 1250 EUR gestor figure reconciles; `.vault/audit/`.
- [ ] `W07.P34.S122` - consolidate findings and expand this plan in place; `.vault/plan/2026-05-26-cross-domain-continuity-plan.md`.

## Wave `W08` - localisation parity and hygiene

Seventeen hardcoded f-strings in _actions.py. --output-language parity gap on auth_clear and others. _errors.py unneeded re-exports. Mixed-language payloads.

### Phase `W08.P35` - de-hardcode error messages in application modelo _actions.py

Seventeen raise error f-string sites; each gets a locale key plus tr. One Step per site keeps the diff per-Step reviewable.

- [ ] `W08.P35.S123` - de-hardcode ledger preflight blocks modelo calculation message; `src/aeat/application/modelo/_actions.py`.
- [ ] `W08.P35.S124` - de-hardcode caller binding values cannot override bucket-derived source bindings message first site; `src/aeat/application/modelo/_actions.py`.
- [ ] `W08.P35.S125` - de-hardcode caller binding values cannot override bucket-derived source bindings message second site; `src/aeat/application/modelo/_actions.py`.
- [ ] `W08.P35.S126` - de-hardcode registry snapshot for modelo missing message; `src/aeat/application/modelo/_actions.py`.
- [ ] `W08.P35.S127` - de-hardcode site 5 of 17; `src/aeat/application/modelo/_actions.py`.
- [ ] `W08.P35.S128` - de-hardcode site 6 of 17; `src/aeat/application/modelo/_actions.py`.
- [ ] `W08.P35.S129` - de-hardcode site 7 of 17; `src/aeat/application/modelo/_actions.py`.
- [ ] `W08.P35.S130` - de-hardcode site 8 of 17; `src/aeat/application/modelo/_actions.py`.
- [ ] `W08.P35.S131` - de-hardcode site 9 of 17; `src/aeat/application/modelo/_actions.py`.
- [ ] `W08.P35.S132` - de-hardcode site 10 of 17; `src/aeat/application/modelo/_actions.py`.
- [ ] `W08.P35.S133` - de-hardcode site 11 of 17; `src/aeat/application/modelo/_actions.py`.
- [ ] `W08.P35.S134` - de-hardcode site 12 of 17; `src/aeat/application/modelo/_actions.py`.
- [ ] `W08.P35.S135` - de-hardcode site 13 of 17; `src/aeat/application/modelo/_actions.py`.
- [ ] `W08.P35.S136` - de-hardcode site 14 of 17; `src/aeat/application/modelo/_actions.py`.
- [ ] `W08.P35.S137` - de-hardcode site 15 of 17; `src/aeat/application/modelo/_actions.py`.
- [ ] `W08.P35.S138` - de-hardcode site 16 of 17; `src/aeat/application/modelo/_actions.py`.
- [ ] `W08.P35.S139` - de-hardcode site 17 of 17; `src/aeat/application/modelo/_actions.py`.
- [ ] `W08.P35.S140` - Haiku validation sweep over application for any further hardcoded f-string error raises append Step per finding; `src/aeat/application/`.

### Phase `W08.P36` - --output-language parity fix

Register --output-language on every Typer command that emits user-facing text. auth_clear config profile show modelo work calculate and others still missing it.

- [ ] `W08.P36.S141` - register --output-language on auth_clear; `src/aeat/entrypoints/cli/_config/__init__.py`.
- [ ] `W08.P36.S142` - register --output-language on config profile show; `src/aeat/entrypoints/cli/_config/__init__.py`.
- [ ] `W08.P36.S143` - register --output-language on modelo work calculate verify file; `src/aeat/entrypoints/cli/_modelo.py`.
- [ ] `W08.P36.S144` - sweep every Typer command for --output-language presence; `regression test asserts every command accepts the flag; `src/aeat/entrypoints/cli/test_output_language_parity.py`.

### Phase `W08.P37` - unneeded re-export removal

Remove build_error_envelope and json_output_requested from _errors.py __all__; update consumers.

- [ ] `W08.P37.S145` - remove build_error_envelope and json_output_requested from _errors.py __all__ update any importer to import from source module; `src/aeat/entrypoints/cli/_errors.py`.

### Phase `W08.P38` - Wave-8 review and persona re-run BREAKPOINT

Code-reviewer and Catalan and Hungarian preferring personas confirm no message renders in English or Spanish when Catalan or Hungarian selected.

- [ ] `W08.P38.S146` - dispatch vaultspec-code-reviewer against every Wave-8 commit; `.vault/exec/`.
- [ ] `W08.P38.S147` - re-run Catalan-preferring and Hungarian-preferring personas verify no message in wrong language; `.vault/audit/`.
- [ ] `W08.P38.S148` - consolidate findings and expand this plan in place; `.vault/plan/2026-05-26-cross-domain-continuity-plan.md`.

## Wave `W09` - systemic drift cleanup file-by-file catalogue

Bulk of Cluster O. Each Step is a single file drift resolution. Mechanical and ruthlessly thorough.

### Phase `W09.P39` - _missing_refs utility duplication consolidation

Seven identical copies of _missing_refs across _validate modules. Extract to a single helper module and import.

- [ ] `W09.P39.S149` - create _validate_helpers.py with canonical _missing_refs and any other shared validate-helpers; `src/aeat/domain/calculations/registry/_validate_helpers.py`.
- [ ] `W09.P39.S150` - delete duplicate _missing_refs from _validate_algorithms.py and import from _validate_helpers; `src/aeat/domain/calculations/registry/_validate_algorithms.py`.
- [ ] `W09.P39.S151` - same for _validate_constructs.py; `src/aeat/domain/calculations/registry/_validate_constructs.py`.
- [ ] `W09.P39.S152` - same for _validate_dependency_sections.py; `src/aeat/domain/calculations/registry/_validate_dependency_sections.py`.
- [ ] `W09.P39.S153` - same for _validate_exports.py; `src/aeat/domain/calculations/registry/_validate_exports.py`.
- [ ] `W09.P39.S154` - same for _validate_record_sections.py; `src/aeat/domain/calculations/registry/_validate_record_sections.py`.
- [ ] `W09.P39.S155` - same for _validate_revision_sections.py; `src/aeat/domain/calculations/registry/_validate_revision_sections.py`.
- [ ] `W09.P39.S156` - same for _validate_surfaces.py; `src/aeat/domain/calculations/registry/_validate_surfaces.py`.

### Phase `W09.P40` - ledger aggregation duplication pair resolution

Three structurally identical guard pairs between _iva_ledger.py and _renta_ledger.py: currency business-classification branch and business-proportion extraction.

- [ ] `W09.P40.S157` - extract shared currency-not-EUR guard to _shared_issue_reasons.py or sibling helper remove duplicates; `src/aeat/application/aggregation/`.
- [ ] `W09.P40.S158` - extract shared business-classification branch PERSONAL_TRANSACTION vs UNCLASSIFIED_BUSINESS_STATE remove duplicates; `src/aeat/application/aggregation/`.
- [ ] `W09.P40.S159` - extract shared business-proportion dispatch BUSINESS full MIXED pct else None remove duplicates; `src/aeat/application/aggregation/`.

### Phase `W09.P41` - dead stored data dual default ghost comment removal

address_postcode unused dual IVARegime.GENERAL and CCAA.MADRID defaults ProfileExportBundle ghost comment dead _profile_binding_selectors alias.

- [ ] `W09.P41.S160` - delete address_postcode field from SetupAnswers or wire to real consumer recommend delete; `src/aeat/application/wizard/_setup_answers.py`.
- [ ] `W09.P41.S161` - replace dual IVARegime.GENERAL defaults with single shared constant; `src/aeat/application/wizard/`.
- [ ] `W09.P41.S162` - replace dual CCAA.MADRID defaults with single shared constant; `src/aeat/application/wizard/`.
- [ ] `W09.P41.S163` - delete ghost ProfileExportBundle comment; `src/aeat/application/user_profile/__init__.py`.
- [ ] `W09.P41.S164` - delete dead alias _profile_binding_selectors; `src/aeat/domain/user_profile/_registry_contract.py`.
- [ ] `W09.P41.S198` - delete duplicate AuthProviderReservedError registration; `the class is registered twice at lines 62-65 and 106-109; `src/aeat/core/errors/registry/_application.py`.
- [ ] `W09.P41.S199` - delete duplicate AuthConfigureDanglingActiveProfileError registration; `the class is registered twice at lines 84-92 and 95-103; `src/aeat/core/errors/registry/_application.py`.
- [ ] `W09.P41.S200` - consolidate the two divergent _decimal_value helpers; `the modelo binding variant has bool-sentinel handling the borrador variant does not; extract one canonical helper and import; `src/aeat/application/modelo/`.
- [ ] `W09.P41.S201` - delete dead __all__ re-exports of build_error_envelope and json_output_requested from _errors.py; `cb0c684f8 follow-up after architecture-specialist surfaced the source-hygiene gap; `src/aeat/entrypoints/cli/_errors.py`.
- [ ] `W09.P41.S202` - audit stored-data drift taxonomy semantic gap; `class lives under errors.refused.* REFUSED category but stored-data drift is semantically an integrity failure not a safety refusal; decide whether to rename and re-emit telemetry or document the semantic exception; `src/aeat/core/errors/registry/_entrypoints.py`.

### Phase `W09.P42` - twin function merge

active_bucket_id_or_raise and require_active_bucket_id have identical bodies. Merge to one canonical function.

- [ ] `W09.P42.S165` - merge active_bucket_id_or_raise and require_active_bucket_id into one canonical function update all call sites; `src/aeat/application/workflow/_models.py`.

### Phase `W09.P43` - side-effect re-export refactor

_language_resolver import for side-effect under private name; replace with explicit register_language_resolver call.

- [ ] `W09.P43.S166` - replace side-effect _language_resolver import with explicit register_language_resolver call in known initialiser; `src/aeat/application/user_profile/__init__.py`.

### Phase `W09.P44` - hardcoded preflight binding-source set

_LEDGER_PREFLIGHT_BINDING_SOURCES is hardcoded frozenset replace with registry-sourced derivation.

- [ ] `W09.P44.S167` - replace _LEDGER_PREFLIGHT_BINDING_SOURCES hardcoded frozenset with registry-sourced derivation; `src/aeat/application/state_projection.py`.

### Phase `W09.P45` - locale _covered_by_namespace duplication

_covered_by_namespace defined identically in two locale modules extract to one.

- [ ] `W09.P45.S168` - extract _covered_by_namespace to one location and import from the other; `src/aeat/locales/`.
- [ ] `W09.P45.S203` - fix 5 i18n ORPHAN placeholders surfaced by S32 parity validator; `either supply missing kwargs at tr call sites or remove orphan placeholders from locale; keys: cli.app.ledger.inventory.unknown_movement_kind kind; cli.app.ledger.ratios.no_override_error bucket_id and category; cli.app.ledger.ratios.unknown_category raw; cli.app.modelo.work.resume_invalid_target target; `src/aeat/`.
- [ ] `W09.P45.S204` - fix 27 i18n SURPLUS kwargs surfaced by S32 parity validator; `either add placeholders to locale text or remove dead kwargs from tr call sites; affected keys include application.auth.operator.errors.unreadable_active_profile cli.common.errors.invalid_iso_date cli.common.errors.period_unrecognised cli.diagnostics.summary.* cli.diagnostics.version.* cli.ledger.errors.filter_parse_error cli.operator_surface.errors.contract_not_accepted cli.operator_surface.landing.*; `src/aeat/`.

### Phase `W09.P46` - modelo period-handling site count audit

Project-wide grep for every period-token-handling function coverage matrix converge any survivors of Wave 1.

- [ ] `W09.P46.S169` - project-wide grep for every period-token-handling function produce coverage matrix; `if more than one site survives Wave 1 append Steps to converge; `src/aeat/`.

### Phase `W09.P47` - --verbose flag usage audit

For every CLI command registering --verbose assert it actually consumes the flag in its rendering path.

- [ ] `W09.P47.S170` - for every CLI command registering --verbose assert it consumes the flag fix or remove unused declarations; `src/aeat/entrypoints/cli/`.

### Phase `W09.P48` - Sonnet drift verification pass

Dispatch Sonnet drift-verification over every file Wave 9 touched fails loudly on remaining duplication shim or re-export.

- [ ] `W09.P48.S171` - dispatch Sonnet drift-verification agent over every Wave-9 touched file fails loudly on remaining duplication shim or re-export; `src/aeat/`.

### Phase `W09.P49` - Wave-9 review and persona re-run BREAKPOINT

Code-reviewer fresh Haiku swarm over 1400 plus files full round-6 fleet repeated plus new tax shapes consolidate expand plan.

- [ ] `W09.P49.S172` - dispatch vaultspec-code-reviewer against every Wave-9 commit; `.vault/exec/`.
- [ ] `W09.P49.S173` - dispatch fresh Haiku discovery swarm over 1400 plus files for drift surviving Wave 9 append Step per finding; `src/aeat/`.
- [ ] `W09.P49.S174` - re-run full round-6 persona fleet plus new tax shapes sociedad civil comunidad de bienes autonomo objetiva trabajador asalariado pensioner with foreign pension; `.vault/audit/`.
- [ ] `W09.P49.S175` - consolidate findings and expand this plan in place; `.vault/plan/2026-05-26-cross-domain-continuity-plan.md`.

## Wave `W10` - registry deadline-window backfill

Eight modelos have zero deadline_windows across all revisions: 100 111 180 232 349 390 entirely; 131 has no revisions; 123 130 200 partial. Backfill each.

### Phase `W10.P50` - Modelo 100 deadline windows for 2020 2021 2022 2024 (round-2 R1 follow-up)

Modelo 100 has six revisions but zero deadline_windows. Register windows where corpus authority exists; document the gaps where it does not.

- [ ] `W10.P50.S176` - register Modelo 100 deadline windows for exercise 2020 campana filing 2021 requires corpus authority; `src/aeat/_data/registry/aeat/modelos/100/revisions/2020/deadline_windows/`.
- [ ] `W10.P50.S177` - register Modelo 100 deadline windows for exercise 2021; `src/aeat/_data/registry/aeat/modelos/100/revisions/2021/deadline_windows/`.
- [ ] `W10.P50.S178` - register Modelo 100 deadline windows for exercise 2022; `src/aeat/_data/registry/aeat/modelos/100/revisions/2022/deadline_windows/`.
- [ ] `W10.P50.S179` - register Modelo 100 deadline windows for exercise 2024 currently tracked as task 42 gated on Orden HAC 242-2025 corpus landing; `src/aeat/_data/registry/aeat/modelos/100/revisions/2024/deadline_windows/`.

### Phase `W10.P51` - Modelo 111 deadline windows

Modelo 111 has zero deadline_windows. Register 2025 and 2026 quarterly windows grounded in BOE Orden.

- [ ] `W10.P51.S180` - register Modelo 111 deadline windows for 2025 quarters 1T 2T 3T 4T BOE Orden grounding required; `src/aeat/_data/registry/aeat/modelos/111/`.
- [ ] `W10.P51.S181` - register Modelo 111 deadline windows for 2026 quarters; `src/aeat/_data/registry/aeat/modelos/111/`.

### Phase `W10.P52` - Modelo 180 deadline windows

Modelo 180 has zero deadline_windows across both revisions. Register annual filing window January for prior year.

- [ ] `W10.P52.S182` - register Modelo 180 annual deadline windows filing in January for prior year 2025 and 2026; `src/aeat/_data/registry/aeat/modelos/180/`.

### Phase `W10.P53` - Modelo 232 deadline windows

Modelo 232 has zero deadline_windows across both revisions. Register annual filing window November for prior year.

- [ ] `W10.P53.S183` - register Modelo 232 annual deadline windows filing in November for prior year 2025 and 2026; `src/aeat/_data/registry/aeat/modelos/232/`.

### Phase `W10.P54` - Modelo 349 deadline windows

Modelo 349 has zero deadline_windows. Register quarterly and above-threshold monthly windows for 2025 and 2026.

- [ ] `W10.P54.S184` - register Modelo 349 quarterly and monthly above-threshold deadline windows for 2025 and 2026; `src/aeat/_data/registry/aeat/modelos/349/`.

### Phase `W10.P55` - Modelo 390 deadline windows

Modelo 390 has zero deadline_windows. Register annual IVA-summary window filing in January for 2025 and 2026.

- [ ] `W10.P55.S185` - register Modelo 390 annual deadline windows filing in January for 2025 and 2026; `src/aeat/_data/registry/aeat/modelos/390.toml`.

### Phase `W10.P56` - Modelo 131 revision population

Modelo 131 directory has zero revisions. Decide scope: scaffold a revision or document the exclusion.

- [ ] `W10.P56.S186` - decide whether Modelo 131 IRPF objective estimation is in scope; `if yes scaffold a revision with casillas and deadline_windows; if no document exclusion; `src/aeat/_data/registry/aeat/modelos/131/`.

### Phase `W10.P57` - Modelo 200 and 202 corporate calendar completion

Modelo 200 has only 2024 windows no 2025; Modelo 202 has 2025-y-siguientes coordinate with foreign-WIP parallel campaign.

- [ ] `W10.P57.S187` - register Modelo 200 deadline windows for 2025 fiscal year filing in July 2026; `src/aeat/_data/registry/aeat/modelos/200/`.
- [ ] `W10.P57.S188` - verify foreign-WIP Modelo 202 corporate-calendar work lands cleanly; `coordinate with parallel campaign; `src/aeat/_data/registry/aeat/modelos/202/`.

### Phase `W10.P58` - Wave-10 review and persona re-run BREAKPOINT

Code-reviewer and full persona fleet verify every previously-absent calendar entry now appears.

- [ ] `W10.P58.S189` - dispatch vaultspec-code-reviewer against every Wave-10 commit; `.vault/exec/`.
- [ ] `W10.P58.S190` - re-run round-6 personas verify every previously-absent calendar entry now appears; `.vault/audit/`.
- [ ] `W10.P58.S191` - consolidate findings and expand this plan in place; `.vault/plan/2026-05-26-cross-domain-continuity-plan.md`.

## Wave `W11` - loop integration and open-ended expansion contract

Campaign governance scaffolding. Does not complete in the conventional sense; codifies open-ended self-driven nature of the campaign.

### Phase `W11.P59` - the expansion contract

At every Wave terminus coordinator dispatches code-reviewer fresh persona fleet Haiku drift sweep Sonnet grounding; each terminus produces a new audit document and expands THIS plan in place.

- [ ] `W11.P59.S192` - at every Wave terminus dispatch code-reviewer on every Wave commit fresh persona fleet of at least five distinct tax shapes Haiku drift sweep on touched files Sonnet grounding on any new BLOCKER or MAJOR; `.vault/exec/`.
- [ ] `W11.P59.S193` - each Wave terminus produces new audit document via vaultspec CLI; `.vault/audit/`.
- [ ] `W11.P59.S194` - each Wave terminus expands THIS plan in place every new BLOCKER MAJOR drift becomes a new Step or Phase or Wave; `.vault/plan/2026-05-26-cross-domain-continuity-plan.md`.
- [ ] `W11.P59.S195` - vault plan check must remain green after every plan expansion; `.vault/plan/2026-05-26-cross-domain-continuity-plan.md`.

### Phase `W11.P60` - termination criteria

Campaign terminates only when full persona-fleet pass returns zero BLOCKER zero MAJOR AND full Haiku drift sweep returns zero in-scope drift AND vault check all returns clean of new campaign-introduced findings.

- [ ] `W11.P60.S196` - campaign terminates only when full persona-fleet pass minimum five distinct shapes returns zero BLOCKER and zero MAJOR AND full Haiku drift sweep returns zero in-scope drift across 1400 plus Python files AND vault check all reports vault clean of new findings; `.vault/audit/`.
- [ ] `W11.P60.S197` - until termination criteria hold every complete claim is treated as premature; `plan re-expands at next loop; `.vault/plan/2026-05-26-cross-domain-continuity-plan.md`.
