---
tags:
  - '#plan'
  - '#cross-domain-continuity'
date: '2026-05-26'
modified: '2026-05-26'
tier: L4
related:
  - '[[2026-05-26-cross-domain-continuity-audit]]'
  - '[[2026-05-26-cli-testimonial-audit]]'
  - '[[2026-05-21-cli-testimonial-audit]]'
  - '[[2026-05-26-corporate-tax-runtime-plan]]'
  - '[[2026-05-21-taxpayer-type-applicability-plan]]'
  - '[[2026-05-26-cross-domain-continuity-adr]]'
  - '[[2026-06-04-cross-domain-continuity-research]]'
---
<!-- RETIRED: P02, P64, S01 -->

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
- [ ] `W01.P07.S233` - R7-INES-7 fix period token notation inconsistency in overview backlog; `M111 surfaces as 2026Q1 while the rest of the system uses 1T; consolidate period rendering through parse_canonical_period output form so backlog and calendar agree; `src/aeat/application/overview/`.

### Phase `W01.P08` - i18n placeholder validator silent-swallow elimination

_interpolate swallows KeyError on placeholder context mismatches and emits half-rendered text. Fix the immediate bracket_no_window mismatch and add an i18n-stack validation step.

- [x] `W01.P08.S30` - rename context key filing_date to as_of at the bracket_no_window raise site; `src/aeat/domain/calculations/registry/_formula_runtime.py`.
- [x] `W01.P08.S31` - strengthen _interpolate to emit developer-visible warning on unmatched placeholders; `src/aeat/core/i18n/_render.py`.
- [x] `W01.P08.S32` - add project-wide i18n placeholder parity validator over every tr call site; `src/aeat/core/i18n/test_placeholder_parity.py`.

### Phase `W01.P09` - Wave-1 review and persona re-run and plan expansion BREAKPOINT

Mandated breakpoint. Dispatch code-reviewer on Wave-1 commits, round-7 persona fleet, fresh Haiku drift sweep on touched files, consolidate findings audit, EXPAND this plan in place with every new BLOCKER MAJOR.

- [x] `W01.P09.S33` - dispatch vaultspec-code-reviewer against every Wave-1 commit and consolidate verdict; `.vault/exec/`.
- [x] `W01.P09.S34` - dispatch round-7 persona fleet minimum five distinct tax shapes including one round-6 repeat; `.vault/audit/`.
- [x] `W01.P09.S35` - dispatch fresh Haiku drift sweep over Wave-1 touched files to confirm no new drift; `src/aeat/`.
- [x] `W01.P09.S36` - consolidate round-7 findings into a new audit document via vaultspec CLI; `.vault/audit/`.
- [x] `W01.P09.S37` - expand this plan in place: every new BLOCKER and MAJOR becomes a new Phase or Step in the appropriate Wave; `re-run vault plan check; `.vault/plan/2026-05-26-cross-domain-continuity-plan.md`.

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

- [x] `W02.P11.S43` - confirm _MODELO_APPLICABILITY_RULES is the canonical modelo-level applicability authority; `add module docstring documenting that modelo-level rules live in Python while window-level applicability_conditions live on ModeloDeadlineWindow registry slot; audit the 18 modelos to ensure every rule populates applicable_entity_types required_income_categories required_estimation_regimes and required_payer_fact where the modelo demands those axes; `src/aeat/domain/calculations/registry/_applicability.py`.
- [x] `W02.P11.S44` - replace the hardcoded 5-entry _GATING_FIELDS dict with a derivation from _MODELO_APPLICABILITY_RULES; `for each rule emit profile_key modelos message_key fix_command tuples covering income-categories entity-types estimation-regimes payer-facts; the resulting projection must be a function not a dict so it stays in sync as rules evolve; `src/aeat/application/overview/__init__.py`.
- [x] `W02.P11.S45` - add calendar-side diagnostic surface --show-suppressed surfacing every obligation the calendar dropped and the verdict reason; `src/aeat/application/overview/__init__.py`.
- [x] `W02.P11.S46` - regression test asserting build_overview_explain and build_overview_calendar produce identical ApplicabilityVerdict per modelo for the same profile; `pin the current correct agreement state to prevent future drift; `src/aeat/application/overview/test_calendar_applicability_consistency.py`.
- [x] `W02.P11.S227` - R7-INES-1 CRITICAL fix overview calendar so Modelos 200 and 202 appear for LEGAL_ENTITY profiles; `today applicable=true via explain but calendar entries are absent for IS modelos; only M349 surfaces in the calendar for an SA with INCN 18.4M; calendar applicability gate diverges from explain applicability; `src/aeat/application/overview/`.
- [x] `W02.P11.S228` - R7-INES-2 CRITICAL fix profile-fact key-namespace divergence between persistence and calendar lookup; `third_party_transactions_above_347_threshold persists as obligations.third_party_transactions_above_347_threshold via config profile show but calendar reads it as unset and warns the key is not declared; same defect class as W01.P05 boolean canonical drift but in a different namespace; `src/aeat/application/overview/__init__.py`.
- [x] `W02.P11.S230` - R7-INES-4 fix Modelo 303 SII monthly cadence; `work create --period 01 accepted but bindings list --period 01 returns no revision for that period; SII-enrolled profiles must have monthly periods 01-12 accepted by the calculate path not just create; `src/aeat/_data/registry/aeat/modelos/303/`.
- [x] `W02.P11.S306` - add --all-profiles flag at the CLI layer for aeat app overview calendar (and follow-on for status explain agenda); `build_overview_calendar is pure; iterate list_profile_buckets and call once per profile, then concatenate entries; same pattern applies to status explain agenda as follow-on; `src/aeat/entrypoints/cli/_overview.py`.
- [ ] `W02.P11.S325` - R9-MANUEL-C M303/M390/M111 applicability over-restrictive for attribution_entity; `profile with iva.regime=GENERAL and withholding.has_employees=true and entity_type=attribution_entity should be applicable for M303/M390/M111 (SC is an IVA-taxable entity even if IRPF flows to socios); refusal can only be bypassed via --allow-not-applicable today; fix applicability rules in _MODELO_APPLICABILITY_RULES; `src/aeat/domain/calculations/registry/_applicability.py`.
- [ ] `W02.P11.S344` - R9-ANDREA-HIGH M130 and M303 backlog from 2022-2023 invisible in overview backlog and overview calendar; `even with 12 work units explicitly created the calendar shows nothing for those years' M130; obligation surface needs to enumerate created work units in addition to (or as enhancement of) registry-derived deadline windows; `src/aeat/application/overview/`.
- [ ] `W02.P11.S363` - R9-ROBERTO-HIGH model property use_type as first-class enum on Transaction or rental input model; `today casillas exist for distintos usos (0065 situacion clave 0073 a disposicion 0074 accesorio 0075 arrendamiento 0082 local de negocio 0085 dias) but no semantic discriminator prevents operator from marking 0100=1 (reducción solicitada) on a vivienda turística; add use_type enum (VIVIENDA_HABITUAL / VIVIENDA_TURISTICA / LOCAL_COMERCIAL / OTROS) and cross-validate against reducción flag; `src/aeat/domain/user_profile/_schema.py`.

### Phase `W02.P12` - Modelo 202 modality gate wiring Cluster Q

derive_modelo_202_modality is orphaned in the domain. Casillas 03 and 32 compute unconditionally. INCN is not a registry binding for Modelo 202.

- [x] `W02.P12.S47` - add an INCN profile binding to the Modelo 202 2025-y-siguientes revision; `src/aeat/_data/registry/aeat/modelos/202/revisions/2025-y-siguientes/bindings/`.
- [x] `W02.P12.S48` - add the modality gate as a registry-level applicability condition on casillas 03 and 32; `src/aeat/_data/registry/aeat/modelos/202/revisions/2025-y-siguientes/casillas/`.
- [x] `W02.P12.S49` - wire derive_modelo_202_modality into registry formula composition as a guard predicate OR remove the orphan function; `src/aeat/domain/calculations/registry/_applicability.py`.
- [x] `W02.P12.S50` - end-to-end CLI test: SL with INCN above 6.000.000 EUR gets only Art. 40.3; `below threshold both modalities reachable; `src/aeat/entrypoints/cli/test_modelo_202_modality.py`.
- [x] `W02.P12.S220` - R7-003 reject invalid period token at modelo work create time not at calculate time; `M202 currently accepts --period 1T at create then fails calculate with no-revision-for-period; period validation must fire at create using the modelo revision's declared period catalogue; `src/aeat/entrypoints/cli/_modelo.py`.

### Phase `W02.P13` - Wave-2 review and persona re-run and plan expansion BREAKPOINT

Mandated breakpoint. Dispatch code-reviewer, round-8 persona fleet focused on cross-domain applicability, Sonnet grounding on calendar to applicability join, consolidate findings, expand plan in place.

- [x] `W02.P13.S51` - dispatch vaultspec-code-reviewer against every Wave-2 commit; `.vault/exec/`.
- [ ] `W02.P13.S52` - dispatch round-8 persona fleet (landlord autonomo SL gestor multi-profile) CLI only; `.vault/audit/`.
- [ ] `W02.P13.S53` - dispatch Sonnet grounding pass against calendar to applicability join to confirm unification holds; `src/aeat/application/overview/`.
- [x] `W02.P13.S54` - consolidate round-8 findings into new audit document via vaultspec CLI and expand this plan in place; `.vault/audit/`.

## Wave `W03` - corporate-tax-runtime hardening

The corporate-tax-runtime plan 8 of 8 Steps complete claim was premature: Clusters D Q R S T are real regressions visible to a real SL operator. Wave 3 closes them.

### Phase `W03.P14` - pyme bracket_table temporal coverage Cluster R

is.modelo-200.tipo-gravamen-pyme brackets cover 2025+ only inside a revision named 2024-y-siguientes. Resolve.

- [x] `W03.P14.S55` - decide and document either backfill 2024 pyme brackets at LIS Art. 29 2024 rate OR revise the revision identity so 2024 routes elsewhere; `.vault/exec/`.
- [x] `W03.P14.S56` - apply the chosen fix to the parameter; `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/records/parameters.toml`.
- [x] `W03.P14.S57` - add registry-validation check that every bracket_table parameter brackets cover the revision declared date range; `src/aeat/domain/calculations/registry/_validate_revision_rules.py`.
- [x] `W03.P14.S58` - regression test: Modelo 200 work unit with 2024 filing_period and micro-empresa profile calculates without bracket_no_window; `src/aeat/domain/calculations/registry/test_modelo_200_temporal_coverage.py`.
- [x] `W03.P14.S218` - CRITICAL BLOCKER R7-001 fix M200 verify path ModeloBuilderError: legal_entity_form binding is a string enum sl/sa but _decimal_inputs_for_ids tries to convert to Decimal; `M200 verify completely broken for corporate profiles; investigate _decimal_inputs_for_ids in application filing to type-discriminate enum bindings from decimal bindings; verify path must support all binding kinds not only Decimal; `src/aeat/application/filing/__init__.py`.
- [ ] `W03.P14.S223` - R7-B variant of S218 covers tax-residence-ccaa enum binding in M100 verify path; `fix is the same _decimal_inputs_for_ids type-discrimination from S218; this Step pins regression coverage explicitly for the M100 CCAA case so a future M200-only fix does not regress M100; `src/aeat/application/filing/__init__.py`.

### Phase `W03.P15` - Modelo 200 base imponible input casilla resolution Cluster D.3

Casilla 552 IS manually inputable; the CLI accepts bare numeric 552 but the registry needs DP200014:00552. Normalise.

- [x] `W03.P15.S59` - add CLI normalisation step on --casilla values that resolves bare numeric tokens to qualified PREFIX:NNNNN keys; `src/aeat/entrypoints/cli/_modelo.py`.
- [x] `W03.P15.S60` - improve the unknown casilla error message to suggest the qualified form when bare numeric provided; `src/aeat/entrypoints/cli/_modelo.py`.
- [x] `W03.P15.S61` - regression test asserting --casilla 552=85000 is accepted and routes to DP200014:00552; `src/aeat/entrypoints/cli/test_modelo_casilla_normalisation.py`.

### Phase `W03.P16` - profile-fact resolution audit Cluster T

Every renta-2025-profile-* binding shows missing despite the fact existing on the profile. Audit the selector projection chain.

- [x] `W03.P16.S62` - for every renta-2025-profile-* binding list selector.field value and verify against canonical profile-fact path wizard emits; `src/aeat/_data/registry/aeat/modelos/100/revisions/2025/bindings/`.
- [x] `W03.P16.S63` - confirm via schema audit that no other modelo (200 202 303 etc) has registered profile-sourced bindings today; `if findings surface a profile binding declared elsewhere; add it to the validation pass; otherwise close S63 as confirmed-empty with a note that S62 already covers the only modelo (100) with profile bindings; `src/aeat/_data/registry/aeat/modelos/`.
- [x] `W03.P16.S64` - identify the mismatch class key-namespace missing projection arm schema-version drift; `apply canonical fix at correct boundary; `src/aeat/application/modelo/_profile_binding.py`.
- [x] `W03.P16.S65` - regression test constructing realistic profile and asserting every renta-2025-profile-* binding resolves to stored fact; `src/aeat/application/modelo/test_profile_binding_real_path.py`.

### Phase `W03.P17` - end-to-end CLI test coverage through real profile to binding path

Corporate-tax-runtime test suite bypassed _profile_binding.py by passing Decimal values directly. Add real-CLI coverage so this regression class cannot recur.

- [x] `W03.P17.S66` - for every Modelo 200 202 303 130 100 calculation lane add CLI-level test that creates a profile via aeat config profile create flows through wizard persistence and runs calculation asserting cuota matches external oracle; `src/aeat/entrypoints/cli/test_modelo_calculation_through_real_cli.py`.
- [x] `W03.P17.S67` - backfill external oracles for cuota assertions: AEAT Manual de Sociedades Modelo 200, AEAT folleto Modelo 130, AEAT Manual de IVA Modelo 303, AEAT Manual de Renta Modelo 100; `src/aeat/entrypoints/cli/test_modelo_calculation_through_real_cli.py`.

### Phase `W03.P18` - Wave-3 review and persona re-run and plan expansion BREAKPOINT

Mandated breakpoint. Code-reviewer, repeat Joan SL persona plus fresh sociedad-anonima, repeat Pere pensioner-landlord, consolidate findings, expand plan in place.

- [x] `W03.P18.S68` - dispatch vaultspec-code-reviewer against every Wave-3 commit; `.vault/exec/`.
- [ ] `W03.P18.S69` - re-run round-6 Joan SL persona to confirm every B-JOAN-* finding closed; `plus fresh sociedad-anonima persona; `.vault/audit/`.
- [ ] `W03.P18.S70` - re-run round-6 Pere pensioner-landlord to confirm Cluster T closed and the IRPF tarifa is applied; `.vault/audit/`.
- [x] `W03.P18.S71` - consolidate findings and expand this plan in place; `.vault/plan/2026-05-26-cross-domain-continuity-plan.md`.

## Wave `W04` - verification semantics

verify rubber-stamps substantively empty drafts because every casilla in Modelo 130 is required false. Extend the verify contract to include substantive predicates.

### Phase `W04.P19` - substantive verification predicates

Decide and implement substantive predicates on the registry side so empty drafts no longer trivially pass verification.

- [x] `W04.P19.S72` - land a new ADR documenting the two-layer verification strategy: layer 1 per-casilla CasillaDefinition.required boolean for single-casilla mandatory gates layer 2 ModeloRevision.verification_predicates tuple for cross-casilla invariants feeding BLOCKING_RULE finding; `minimal DSL all_nonzero any_nonzero in W04; complex DSL deferred to W09; `.vault/adr/`.
- [x] `W04.P19.S73` - mark mandatory casillas required=true in Modelo 130 TOML per BOE AEAT form instructions; `layer 1 of hybrid verification strategy; `src/aeat/_data/registry/aeat/modelos/130.toml`.
- [x] `W04.P19.S74` - mark mandatory casillas required=true in Modelo 100 303 200 202 TOML per BOE AEAT form instructions; `same layer-1 pattern as S73; `src/aeat/_data/registry/aeat/modelos/`.
- [x] `W04.P19.S75` - extend _required_input_casillas_for_revision and _classify_verification_outcome to honour the new CasillaDefinition.required field plus minimal VerificationPredicateDefinition DSL (all_nonzero any_nonzero); `BLOCKING_RULE finding kind; include unit test for predicate evaluator; `src/aeat/application/modelo/_actions.py`.
- [x] `W04.P19.S76` - regression test that Modelo 130 with all casillas zero is no longer verificado_completo; `src/aeat/application/modelo/test_verification_substance.py`.
- [x] `W04.P19.S210` - wire post-calculation casilla observation provenance re-validation into verify path; `current verify in _collect_revision_verification_findings only checks input key existence not legal_refs source_refs formula_id integrity; tampering a persisted casilla value silently slips through; add typed drift detection and refuse VERIFICADO_COMPLETO on observation mismatch; `src/aeat/application/modelo/_actions.py`.
- [x] `W04.P19.S211` - regression test that mutating a persisted casilla value on disk between calculate and verify is caught by the new provenance re-validation; `deliberate tampering scenario currently absent from test_file_flow test_verify_ suite; `src/aeat/application/modelo/test_verification_substance.py`.
- [x] `W04.P19.S296` - fix M200 DP200014:00562 casilla TOML misclassification  -  change input_kind from manual to computed and required from true to false in liquidacion-00562-cuota-integra.toml; `no verifier code change required; add regression test asserting M200 revision with DP200014:00562 present only in casilla_values engine-computed reaches VERIFICADO_COMPLETO without MISSING_REQUIRED_CASILLA finding; scope confirmed to ONE casilla across M100/M200/M202/M303; `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/casillas/liquidacion-00562-cuota-integra.toml`.
- [x] `W04.P19.S305` - ROOT CAUSE CORRECTED: not the session-nesting issue claimed by Nuria persona but the fail-closed exception handler in _refuse_duplicate_tax_id at _profile_repository.py line 668; `one unreadable existing profile currently blocks creating ANY new profile even for a completely different NIF; change except Exception handler to warn-and-continue and only raise on a confirmed duplicate NIF match; gestor multi-profile workflow unblocks immediately; `src/aeat/application/user_profile/_profile_repository.py`.
- [x] `W04.P19.S340` - R9-ANDREA-S340 small fix  -  workflow engine DRAFT_HAS_ERRORS abort path does NOT surface the verification findings to operator; `findings ARE produced and persisted (retrievable via aeat app modelo work verification-report list) but the abort emits only the status_value; extend WorkflowStep.details (and CLI render of the abort) to include verification_report_id + a pointer like 'Run aeat app modelo work verification-report list {revision_id}'; no new command needed verification-report list already exists; `src/aeat/application/modelo/_engine.py`.
- [x] `W04.P19.S376` - extend Layer 2 verification DSL with implies_nonzero conditional operator per dsl-conditional-predicate ADR; `register operator name in KNOWN_VERIFICATION_PREDICATE_OPERATORS and extend VerificationPredicateDefinition docstring with the strictly-positive antecedent semantics; `src/aeat/domain/calculations/registry/_schema.py`.
- [x] `W04.P19.S377` - add _PREDICATE_IMPLIES_NONZERO regex + branch in _evaluate_predicate_expression alongside cap_le_when_positive following the ADR semantics (antecedent strictly positive triggers consequent non-zero requirement; `antecedent zero or negative trivially holds); `src/aeat/application/modelo/_actions.py`.
- [x] `W04.P19.S378` - add five-case unit-test suite for implies_nonzero (antecedent zero, negative, both positive, violated when consequent zero, unknown consequent treated as zero) plus extend the P10.S68 lock-step gate fixture so authoring-time validation accepts the new operator; `src/aeat/application/modelo/test_verification_predicates.py`.
- [ ] `W04.P19.S398` - FU-task-226 M131 cuota-minima regulatory floor authoring gated on Orden EHA/672/2007 modulo-tariff corpus landing under task 226; `structural implies_nonzero(C01 C07) attempt rolled back at c159966df because the formula DAG does not connect C01 to C07 via the page-1 chain (C07 = C02+C04+C06 only); this Step now tracks the regulatory-floor predicate authoring waiting for the corpus blocker; `src/aeat/_data/registry/aeat/modelos/131/`.

### Phase `W04.P20` - verification path naming and boundary documentation

Two verify paths exist work-unit gate and PDF cross-check. Document the boundary.

- [x] `W04.P20.S77` - add architectural docstring at modelo init and verification init explaining the boundary; `consider renaming verify_modelo_revision to validate_modelo_revision; `src/aeat/application/`.

### Phase `W04.P21` - Wave-4 review and persona re-run BREAKPOINT

Mandated breakpoint. Code-reviewer and persona-fleet re-run focused on verify path.

- [x] `W04.P21.S78` - dispatch vaultspec-code-reviewer against every Wave-4 commit; `.vault/exec/`.
- [ ] `W04.P21.S79` - re-run Marc autonomo IT and fresh persona reaching work verify confirm verificado_completo refused on empty drafts; `.vault/audit/`.
- [ ] `W04.P21.S80` - consolidate findings and expand this plan in place; `.vault/plan/2026-05-26-cross-domain-continuity-plan.md`.

## Wave `W05` - ledger surface completion

Modelo 130 income side has no ledger aggregation resolver. Non-EUR transactions silently drop. No bulk classify. No IVA-wallet inspector. No classification enums for intracom export suffered retention.

### Phase `W05.P22` - Modelo 130 income-side aggregation resolver

Add the missing LedgerRentaIncomeAggregationSourceResolver and wire it into Modelo 130.

- [x] `W05.P22.S81` - add LedgerRentaIncomeAggregationSourceResolver covering IRPF actividad-economica income side; `src/aeat/application/aggregation/_modelo_bindings.py`.
- [x] `W05.P22.S82` - implement income-side aggregation logic following the expense-side resolver pattern; `src/aeat/application/aggregation/_renta_income_ledger.py`.
- [x] `W05.P22.S83` - register binding modelo-130-actividad-economica-ingresos-cumulative consuming the new resolver; `src/aeat/_data/registry/aeat/modelos/130.toml`.
- [x] `W05.P22.S84` - bind Modelo 130 casilla 01 to the new aggregation result; `src/aeat/_data/registry/aeat/modelos/130.toml`.
- [x] `W05.P22.S85` - regression test real autonomo ledger imports flow into Modelo 130 casilla 01 with expected cumulative ingresos; `src/aeat/application/aggregation/test_renta_income_aggregation.py`.
- [x] `W05.P22.S342` - R9-ANDREA-S342 HEAVY fix  -  _income_business_amount uses raw.amount and ignores taxable_base and irpf_category; `M130 casilla 03 rendimiento neto cannot be aggregated from ledger because there is no taxable_base_sum fact path; (1) add irpf_category=actividad_economica filter to _classify_income_transaction (skip nominas) (2) add fact taxable_base_sum aggregation path (3) update _RentaLedgerIncomeSelector to accept both gross_income_sum and taxable_base_sum (4) add M130 registry binding for casilla 03 pointing to new fact (5) two oracle-grounded tests against RD 439/2007 art 110; `src/aeat/application/aggregation/_renta_income_ledger.py`.
- [x] `W05.P22.S345` - R9-ANDREA-HIGH ledger preflight false-positives on nómina entries; `irpf_category=trabajo implies IVA exemption but preflight marks missing_taxable_base + missing_iva_amount + missing_iva_rate for every INCOMING with category trabajo; teach preflight that trabajo entries are exempt from IVA validation; `src/aeat/application/ledger/_preflight.py`.

### Phase `W05.P23` - FX-conversion contract for non-EUR transactions

_iva_ledger.py and _renta_ledger.py silently drop non-EUR. Adopt single FX-conversion contract.

- [x] `W05.P23.S86` - decide and document FX conversion strategy; `.vault/exec/`.
- [x] `W05.P23.S87` - add fx_rate and value_in_eur fields on Transaction or aggregation row; `src/aeat/domain/transactions/_raw_transaction.py`.
- [x] `W05.P23.S88` - implement chosen FX strategy in import path or aggregation layer; `src/aeat/adapters/inbound/financial/providers/_csv.py`.
- [x] `W05.P23.S89` - replace duplicated currency-not-EUR guards with shared predicate; `src/aeat/application/aggregation/`.
- [x] `W05.P23.S90` - regression test USD invoice imports with FX rate and aggregates with expected EUR value; `src/aeat/application/aggregation/test_fx_conversion.py`.

### Phase `W05.P24` - classification enums for intracom export and suffered retention

ledger classify accepts BUSINESS PERSONAL MIXED but no enums for entrega intracom export non-EU or ingreso con retencion suffered.

- [x] `W05.P24.S91` - add iva_category IvaCategory and counterparty_eu_member_state EUMemberState fields directly on Transaction in domain transactions _models.py; `do NOT extend BusinessClassification with intracom export values per architect verdict; IvaCategory already exists in domain iva _schema.py; blocked on FU-W05-B ADR acceptance; `src/aeat/domain/transactions/_models.py`.
- [x] `W05.P24.S92` - add counterparty_country field on Transaction currently only on Invoice; `src/aeat/domain/transactions/_models.py`.
- [x] `W05.P24.S93` - extend ledger classify CLI to accept new axes; `src/aeat/entrypoints/cli/_ledger.py`.
- [x] `W05.P24.S94` - wire new iva_category and counterparty_eu_member_state axes into IVA aggregation so Modelo 303 casillas 59 and 60 receive their bases; `casilla 62 EXCLUDED from scope (it is the criterio de caja box per art 75 LIVA not an intracom box); also handle the R12 nuance where B2B services to EU customers resolve to DOMESTIC_NOT_SUBJECT not INTRA_COMMUNITY_SUPPLY; `src/aeat/application/aggregation/_iva_ledger.py`.
- [x] `W05.P24.S95` - regression test that an autonomo with intra-community GOODS supply (INTRA_COMMUNITY_SUPPLY iva_category, counterparty_eu_member_state set to a non-ES EU state) populates casilla 59 correctly; `anti-tautology proof mutating counterparty_eu_member_state to ES triggers DOMESTIC_COUNTERPARTY_ON_INTRA_COMMUNITY_TRANSACTION rejection; separate scenario for DOMESTIC_NOT_SUBJECT (R12 B2B services like Marc IT to DE) confirms it does NOT feed casilla 59 per ADR D4; `src/aeat/application/aggregation/test_intracom_export.py`.
- [ ] `W05.P24.S281` - Criterio de caja ledger axis: add criterio_caja IvaCategory variant and wire casilla 62; `separate from intracom/export S94 scope; `src/aeat/application/aggregation/_iva_ledger.py`.
- [ ] `W05.P24.S287` - FU-W05-B author IVA-category-and-counterparty ADR formalising the architect's four decisions: D1 field placement on Transaction not BusinessClassification, D2 no BusinessClassification extension, D3 casilla-62 criterio-de-caja scope exclusion, D4 R12 routing for B2B services to EU customer; `cite Ley 37/1992 articles 25 21 163 quinquies 75; blocks S91 implementation; `.vault/adr/`.

### Phase `W05.P25` - bulk classify CSV-driven and rule-engine

Single-id classify unusable for hundreds of movements. Add bulk path.

- [x] `W05.P25.S96` - implement ledger classify --from-csv parsing CSV into typed BulkClassifyRow pydantic model; `partial-success semantics matching ledger import pattern; BulkClassifyRow BulkClassifyResult BulkClassifyFailure in _models.py; unknown CSV columns rejected pre-persistence; source_command edit_lineage; per architect #118 grounding; `src/aeat/entrypoints/cli/_ledger.py`.
- [x] `W05.P25.S97` - implement rule-based classifier surface ledger rule add description-pattern classification BUSINESS; `src/aeat/entrypoints/cli/_ledger.py`.
- [x] `W05.P25.S98` - regression tests for bulk and rule paths; `src/aeat/entrypoints/cli/test_ledger_bulk_classify.py`.
- [x] `W05.P25.S315` - author rule-engine ADR for W05.P25.S97 ledger classification rules  -  pattern engine choice (regex/substring/glob), storage backend (profile-scoped SecureBoundRepository), conflict policy, rule apply scope (ACTIVE NOT_YET_PROCESSED only), reaffirm interaction; `per architect #118 grounding S97 cannot start until this ADR lands; `.vault/adr/`.

### Phase `W05.P26` - IVA-wallet inspector verb

compensacion-pendiente-anteriores binding consumes previous-filing value but no operator-visible verb queries wallet balance.

- [x] `W05.P26.S99` - add aeat app modelo iva-wallet balance verb; `balance computed from IvaCompensationPeriodState records via build_iva_compensation_carry_forward_report; next_expiry_year=nearest source_filing_year+4 among ACTIVE lots; new IvaWalletBalanceReport in application calculations _iva_wallet_balance.py; per architect #118 grounding; `src/aeat/entrypoints/cli/_modelo.py`.
- [x] `W05.P26.S100` - test sequence Q1-2024 1200 + Q2-2024 apply 300 + Q1-2025 apply 500 with as_of_year=2028 asserts total_balance=400 next_expiry_year=2028; `anti-tautology via mutated applied_amount triggers model_validator ValueError; per architect #118 grounding; `src/aeat/entrypoints/cli/test_iva_wallet_inspector.py`.

### Phase `W05.P27` - Wave-5 review and persona re-run BREAKPOINT

Mandated breakpoint. Code-reviewer and repeat Laia Marc Joan to confirm ledger surface usable end-to-end.

- [x] `W05.P27.S101` - dispatch vaultspec-code-reviewer against every Wave-5 commit; `.vault/exec/`.
- [ ] `W05.P27.S102` - re-run Laia e-commerce OSS UK Marc autonomo intracom and Joan SL intracom confirming OSS 349 UK IVA-wallet handled; `.vault/audit/`.
- [x] `W05.P27.S103` - consolidate findings and expand this plan in place; `.vault/plan/2026-05-26-cross-domain-continuity-plan.md`.

## Wave `W06` - profile portability

Profile export ships identity only Cluster E. Import mints fresh UUIDs Cluster F.

### Phase `W06.P28` - full-bundle export schema

Design and implement a bundled-export schema that carries work units calculation revisions ledger entries and filing records with explicit confidentiality treatment for encrypted material.

- [x] `W06.P28.S104` - design bundled-export schema with explicit confidentiality treatment for encrypted material; `src/aeat/domain/user_profile/_values.py`.
- [x] `W06.P28.S105` - implement bundled serializer with schema-version bumping; `src/aeat/application/user_profile/`.
- [x] `W06.P28.S106` - implement bundled deserializer with provenance preservation; `src/aeat/application/user_profile/`.
- [x] `W06.P28.S107` - real-CLI roundtrip test export non-trivial profile and re-import to fresh storage root every artefact survives; `src/aeat/entrypoints/cli/test_profile_export_roundtrip.py`.
- [x] `W06.P28.S260` - author profile-portability ADR formalising the bundle decision space; `strip encrypted material refuse-on-profile-id-collision schema-version 2 bump typed-pydantic-throughout; cite the W75 grounding section as research basis; required before S104 implementation lands; `.vault/adr/`.

### Phase `W06.P29` - idempotent import

Add an idempotency mode that respects the bundle profile_id when no local profile of that id exists.

- [x] `W06.P29.S108` - add idempotency mode that respects bundle profile_id when no local profile of that id exists and refuses or upserts when one does; `src/aeat/entrypoints/cli/_config/__init__.py`.
- [x] `W06.P29.S109` - regression test re-importing same bundle twice produces one profile not two; `src/aeat/entrypoints/cli/test_profile_import_idempotency.py`.

### Phase `W06.P30` - Wave-6 review and persona re-run BREAKPOINT

Code-reviewer and Nuria gestor multi-profile re-run to confirm bundle now carries work ledger revisions filings.

- [x] `W06.P30.S110` - dispatch vaultspec-code-reviewer against every Wave-6 commit; `.vault/exec/`.
- [x] `W06.P30.S111` - re-run Nuria gestor multi-profile to confirm bundle now carries work and ledger and revisions and filings; `colleague-handover workflow viable; `.vault/audit/`.
- [x] `W06.P30.S112` - consolidate findings and expand this plan in place; `.vault/plan/2026-05-26-cross-domain-continuity-plan.md`.

## Wave `W07` - IRPF tarifa and cross-period surfaces

Pere Modelo 100 returns 0 cuota the IRPF tarifa is not applied. 130 to 100 projection invisible. IVA-wallet not surfaced. Cross-fiscal-year compare verb absent.

### Phase `W07.P31` - IRPF tarifa wiring Cluster P

Trace Modelo 100 cuota path end-to-end for a pensioner-landlord profile and identify where the tarifa is silently zeroed.

- [x] `W07.P31.S113` - trace Modelo 100 cuota path end-to-end for pensioner-landlord and identify where tarifa is silently zeroed; `.vault/exec/`.
- [x] `W07.P31.S114` - confirm root cause class CCAA fact missing or wrong; `profile-fact bindings missing per Cluster T; rate lookup gated on wrong predicate; apply fix at correct boundary; `src/aeat/_data/registry/aeat/modelos/100/`.
- [x] `W07.P31.S115` - regression test Pere profile base 35400 minimo 5550 Catalonia returns Modelo 100 cuota in expected range; `src/aeat/domain/calculations/registry/test_modelo_100_tarifa_real.py`.
- [x] `W07.P31.S246` - FU-W07-B extend Modelo 100 revision 2024 minimo del contribuyente to model LIRPF Art. 57.2/57.3 age supplements (+1150 EUR at 65-74, +1400 EUR at >=75) - required for pensioner personas (Pere, hypothetical >=75) to compute correct cuota; `mirror pattern from base flat 5550 fix in 01ac9d698; `src/aeat/_data/registry/aeat/modelos/100/revisions/2024/`.
- [x] `W07.P31.S247` - FU-W07-B Art. 58 descendant minimo extensions in Modelo 100 revision 2024; `2400/2700/4000/4500 EUR per child supplements based on order and 3000 EUR <3 anos supplement; required for natural-person personas with descendants; `src/aeat/_data/registry/aeat/modelos/100/revisions/2024/`.
- [x] `W07.P31.S248` - FU-W07-B Art. 59 ascendant minimo extensions in Modelo 100 revision 2024; `ascendant over 65 supplements; required for personas claiming dependant parents; `src/aeat/_data/registry/aeat/modelos/100/revisions/2024/`.
- [x] `W07.P31.S249` - FU-W07-B regression test Pere age 70 viudo CCAA Comunidad Valenciana with the age supplement applied returns AEAT-published cuota for the analogous worked example; `supersedes the current 4-test suite which only exercises the base flat minimo; `src/aeat/domain/calculations/registry/test_modelo_100_tarifa_real.py`.
- [ ] `W07.P31.S301` - R8-ROSA-E Cluster T extension casillas 0511 0513 0515 0517 0511 spouse minimo do NOT consume profile renta_family renta_spouse data even though profile carries minor_children_in_unit marital_status spouse_tax_id etc; `add bindings from profile to casilla so motor computes minimo familiar from profile data not requiring manual operator override; `src/aeat/_data/registry/aeat/modelos/100/revisions/2024/bindings/`.
- [x] `W07.P31.S353` - R9-TOMAS-CRITICAL S353 add formula renta-2024-base-liquidable-general-sometida-a-gravamen targeting casilla 0505 expression max(0, 0500 - anualidades_alimentos_hijos_judicial); `change casilla 0505 TOML input_kind from manual to computed in both 2024 and 2025 revisions; G6 gate  -  coder MUST verify the anualidades operand from aeat-dr-100-2024-dictionary in source_refs; if legal grounding cannot be confirmed fall back to input_kind=manual + required=true so verify gate fires; `src/aeat/_data/registry/aeat/modelos/100/revisions/`.
- [x] `W07.P31.S361` - R9-ROBERTO-BLOCKER CRITICAL M100 cuota liquida to cuota diferencial chain broken; `0585/0586 cuota liquida compute correctly but 0587 (total cuota liquida) 0595 (cuota resultante) 0609 (total pagos a cuenta) 0610 (cuota diferencial) and 0670 (resultado declaracion) all stay zero; entire downstream M100 calculation produces zero result; pagos-a-cuenta tramo (0598/0599/0604) accepted as inputs but does not flow to 0609; M100 verify returns DRAFT_HAS_ERRORS for any persona with realistic retención + pagos fraccionados; this is a major formula-graph regression in M100 2024 revision affecting EVERY M100 filer with retenciones; `src/aeat/_data/registry/aeat/modelos/100/revisions/2024/`.
- [ ] `W07.P31.S362` - R9-ROBERTO-BLOCKER Art. 23.2 LIRPF 60 percent reduccion vivienda habitual not auto-computed; `casilla 0100=1 flag accepted but does not trigger a formula on 0149 to populate 0150 (reducción importe); operator must manually compute 60 percent of rendimiento neto and supply --casilla 0150=<value>; without this the contribuyente pays full IRPF on rental income that should be 40 percent taxed; add formula renta-2024-vivienda-habitual-reduccion targeting 0150 expression 0149 times 0.60 when 0100 equals 1; `src/aeat/_data/registry/aeat/modelos/100/revisions/2024/casillas/`.

### Phase `W07.P32` - 130 to 100 projection verb

The binding renta-2025-modelo-130-pagos-fraccionados exists; the projection is invisible from the operator surface.

- [x] `W07.P32.S116` - add aeat app modelo project --target 100 --from 130-revisions verb surfacing projected year-end Modelo 100 from quarterly 130 filings; `src/aeat/entrypoints/cli/_modelo.py`.
- [x] `W07.P32.S117` - regression test series of four filed 130 quarters produces sensible Modelo 100 projection; `src/aeat/entrypoints/cli/test_modelo_projection.py`.

### Phase `W07.P33` - cross-fiscal-year compare verb

Add an aeat app modelo compare verb surfacing prior-period versus current-period casilla deltas.

- [x] `W07.P33.S118` - add aeat app modelo compare --year 2024 --year 2025 --modelo 100 verb surfacing prior-period versus current-period casilla deltas; `src/aeat/entrypoints/cli/_modelo.py`.
- [x] `W07.P33.S119` - regression test against two fiscal years; `src/aeat/entrypoints/cli/test_modelo_compare.py`.

### Phase `W07.P34` - Wave-7 review and persona re-run BREAKPOINT

Code-reviewer and Pere Marc re-run confirming IRPF tarifa applied, 130 to 100 projection discoverable, IVA-wallet queryable.

- [x] `W07.P34.S120` - dispatch vaultspec-code-reviewer against every Wave-7 commit; `.vault/exec/`.
- [ ] `W07.P34.S121` - re-run Pere pensioner-landlord and Marc autonomo to confirm tarifa applied 130-to-100 projection discoverable IVA-wallet queryable Pere 1250 EUR gestor figure reconciles; `.vault/audit/`.
- [x] `W07.P34.S122` - consolidate findings and expand this plan in place; `.vault/plan/2026-05-26-cross-domain-continuity-plan.md`.

## Wave `W08` - localisation parity and hygiene

Seventeen hardcoded f-strings in _actions.py. --output-language parity gap on auth_clear and others. _errors.py unneeded re-exports. Mixed-language payloads.

### Phase `W08.P35` - de-hardcode error messages in application modelo _actions.py

Seventeen raise error f-string sites; each gets a locale key plus tr. One Step per site keeps the diff per-Step reviewable.

- [x] `W08.P35.S123` - de-hardcode ledger preflight blocks modelo calculation message; `src/aeat/application/modelo/_actions.py`.
- [x] `W08.P35.S124` - de-hardcode caller binding values cannot override bucket-derived source bindings message first site; `src/aeat/application/modelo/_actions.py`.
- [x] `W08.P35.S125` - de-hardcode caller binding values cannot override bucket-derived source bindings message second site; `src/aeat/application/modelo/_actions.py`.
- [x] `W08.P35.S126` - de-hardcode registry snapshot for modelo missing message; `src/aeat/application/modelo/_actions.py`.
- [x] `W08.P35.S127` - de-hardcode site 5 of 17; `src/aeat/application/modelo/_actions.py`.
- [x] `W08.P35.S128` - de-hardcode site 6 of 17; `src/aeat/application/modelo/_actions.py`.
- [x] `W08.P35.S129` - de-hardcode site 7 of 17; `src/aeat/application/modelo/_actions.py`.
- [x] `W08.P35.S130` - de-hardcode site 8 of 17; `src/aeat/application/modelo/_actions.py`.
- [x] `W08.P35.S131` - de-hardcode site 9 of 17; `src/aeat/application/modelo/_actions.py`.
- [x] `W08.P35.S132` - de-hardcode site 10 of 17; `src/aeat/application/modelo/_actions.py`.
- [x] `W08.P35.S133` - de-hardcode site 11 of 17; `src/aeat/application/modelo/_actions.py`.
- [x] `W08.P35.S134` - de-hardcode site 12 of 17; `src/aeat/application/modelo/_actions.py`.
- [x] `W08.P35.S135` - de-hardcode site 13 of 17; `src/aeat/application/modelo/_actions.py`.
- [x] `W08.P35.S136` - de-hardcode site 14 of 17; `src/aeat/application/modelo/_actions.py`.
- [x] `W08.P35.S137` - de-hardcode site 15 of 17; `src/aeat/application/modelo/_actions.py`.
- [x] `W08.P35.S138` - de-hardcode site 16 of 17; `src/aeat/application/modelo/_actions.py`.
- [x] `W08.P35.S139` - de-hardcode site 17 of 17; `src/aeat/application/modelo/_actions.py`.
- [x] `W08.P35.S140` - Haiku validation sweep over application for any further hardcoded f-string error raises append Step per finding; `src/aeat/application/`.

### Phase `W08.P36` - --output-language parity fix

Register --output-language on every Typer command that emits user-facing text. auth_clear config profile show modelo work calculate and others still missing it.

- [x] `W08.P36.S141` - register --output-language on auth_clear; `src/aeat/entrypoints/cli/_config/__init__.py`.
- [x] `W08.P36.S142` - register --output-language on config profile show; `src/aeat/entrypoints/cli/_config/__init__.py`.
- [x] `W08.P36.S143` - register --output-language on modelo work calculate verify file; `src/aeat/entrypoints/cli/_modelo.py`.
- [x] `W08.P36.S144` - sweep every Typer command for --output-language presence; `regression test asserts every command accepts the flag; `src/aeat/entrypoints/cli/test_output_language_parity.py`.

### Phase `W08.P37` - unneeded re-export removal

Remove build_error_envelope and json_output_requested from _errors.py __all__; update consumers.

- [x] `W08.P37.S145` - remove build_error_envelope and json_output_requested from _errors.py __all__ update any importer to import from source module; `src/aeat/entrypoints/cli/_errors.py`.

### Phase `W08.P38` - Wave-8 review and persona re-run BREAKPOINT

Code-reviewer and Catalan and Hungarian preferring personas confirm no message renders in English or Spanish when Catalan or Hungarian selected.

- [x] `W08.P38.S146` - dispatch vaultspec-code-reviewer against every Wave-8 commit; `.vault/exec/`.
- [x] `W08.P38.S147` - re-run Catalan-preferring and Hungarian-preferring personas verify no message in wrong language; `.vault/audit/`.
- [x] `W08.P38.S148` - consolidate findings and expand this plan in place; `.vault/plan/2026-05-26-cross-domain-continuity-plan.md`.

## Wave `W09` - systemic drift cleanup file-by-file catalogue

Bulk of Cluster O. Each Step is a single file drift resolution. Mechanical and ruthlessly thorough.

### Phase `W09.P39` - _missing_refs utility duplication consolidation

Seven identical copies of _missing_refs across _validate modules. Extract to a single helper module and import.


### Phase `W09.P40` - ledger aggregation duplication pair resolution

Three structurally identical guard pairs between _iva_ledger.py and _renta_ledger.py: currency business-classification branch and business-proportion extraction.

- [x] `W09.P40.S157` - extract shared currency-not-EUR guard to _shared_issue_reasons.py or sibling helper remove duplicates; `src/aeat/application/aggregation/`.
- [x] `W09.P40.S158` - extract shared business-classification branch PERSONAL_TRANSACTION vs UNCLASSIFIED_BUSINESS_STATE remove duplicates; `src/aeat/application/aggregation/`.
- [x] `W09.P40.S159` - extract shared business-proportion dispatch BUSINESS full MIXED pct else None remove duplicates; `src/aeat/application/aggregation/`.

### Phase `W09.P41` - dead stored data dual default ghost comment removal

address_postcode unused dual IVARegime.GENERAL and CCAA.MADRID defaults ProfileExportBundle ghost comment dead _profile_binding_selectors alias.

- [x] `W09.P41.S160` - delete address_postcode field from SetupAnswers or wire to real consumer recommend delete; `src/aeat/application/wizard/_setup_answers.py`.
- [x] `W09.P41.S161` - replace dual IVARegime.GENERAL defaults with single shared constant; `src/aeat/application/wizard/`.
- [x] `W09.P41.S162` - replace dual CCAA.MADRID defaults with single shared constant; `src/aeat/application/wizard/`.
- [x] `W09.P41.S163` - delete ghost ProfileExportBundle comment; `src/aeat/application/user_profile/__init__.py`.
- [x] `W09.P41.S164` - delete dead alias _profile_binding_selectors; `src/aeat/domain/user_profile/_registry_contract.py`.
- [x] `W09.P41.S198` - delete duplicate AuthProviderReservedError registration; `the class is registered twice at lines 62-65 and 106-109; `src/aeat/core/errors/registry/_application.py`.
- [x] `W09.P41.S199` - delete duplicate AuthConfigureDanglingActiveProfileError registration; `the class is registered twice at lines 84-92 and 95-103; `src/aeat/core/errors/registry/_application.py`.
- [x] `W09.P41.S200` - consolidate the two divergent _decimal_value helpers; `the modelo binding variant has bool-sentinel handling the borrador variant does not; extract one canonical helper and import; `src/aeat/application/modelo/`.
- [x] `W09.P41.S201` - delete dead __all__ re-exports of build_error_envelope and json_output_requested from _errors.py; `cb0c684f8 follow-up after architecture-specialist surfaced the source-hygiene gap; `src/aeat/entrypoints/cli/_errors.py`.
- [x] `W09.P41.S202` - audit stored-data drift taxonomy semantic gap; `class lives under errors.refused.* REFUSED category but stored-data drift is semantically an integrity failure not a safety refusal; decide whether to rename and re-emit telemetry or document the semantic exception; `src/aeat/core/errors/registry/_entrypoints.py`.
- [x] `W09.P41.S205` - consolidate UserProfileLifecycleRepository.__init__ and UserProfileSnapshotRepository.__init__ identical signatures into shared base class or factory; `Wave-1 drift sweep DUPLICATE finding; `src/aeat/application/user_profile/_repository.py`.
- [x] `W09.P41.S206` - remove _I18N_STRICT_PLACEHOLDERS from __all__ in core i18n _render.py; `private names must not be exported; Wave-1 audit FU-C; `src/aeat/core/i18n/_render.py`.
- [x] `W09.P41.S207` - add inline comment in _command_matches_current confirming attachment_ids equality is value-equal not identity-equal; `pydantic-frozen collection safety note; Wave-1 audit FU-E; `src/aeat/application/ledger/_actions.py`.
- [x] `W09.P41.S208` - audit src/aeat/tests/secure_sql.py to confirm isolated_profile_storage_root provisions EphemeralMasterKeyProvider correctly without requiring external get_master_key_provider wrapper; `root cause 78798a3f7 routing commit + require_ready gate rejecting unsecured-backend sessions; the fix is NOT gate relaxation but test-pattern replacement; this Step verifies the existing helper is drop-in ready before S209 batches migrate the 20 affected files; `src/aeat/tests/secure_sql.py`.
- [ ] `W09.P41.S209` - migrate 20 CLI test files from monkeypatch unsecured-backend pattern to isolated_runtime_profile fixture established in test_errors_boundary.py and test_modelo_casilla_normalisation.py; `full file list: test_apex_workflow_verification test_audit_remediation test_cli_surface test_cold_start_no_profile test_command_suggestions test_fast_path_no_state test_modelo_202_modality test_modelo_discovery_defects test_modelo_period_consistency test_modelo_source_mesh_calculate test_modelo_work_applicability_guard test_modelo_work_ux test_profile_create_taxpayer_type_paths test_profile_incn_new_entity_paths test_profile_lifecycle_verbs test_profile_output_language test_repair_bootstrap_exempt test_root_grammar_invariants test_root_help_shape test_session_lifecycle_roundtrip; per-file triage required some may pass with simple env-var removal; `src/aeat/entrypoints/cli/`.
- [x] `W09.P41.S212` - fix Real Decreto-ley 4/2004 legal citation typo in M200 parameters.toml; `Wave-3 audit FU-F; `src/aeat/_data/registry/aeat/modelos/200/`.
- [x] `W09.P41.S213` - add clarifying comment in M100 binding-schema pin test explaining the 30-binding sentinel includes 19 scalar bindings plus 11 family-repeating-collection bindings; `prevents future drift in the sentinel meaning; Wave-3 audit FU-H; `src/aeat/application/modelo/test_profile_binding_real_path.py`.
- [x] `W09.P41.S214` - add StoredTransactionDriftError ValidationError guard to TransactionCatalogueRepository.load() at domain transactions _repository.py line 139; `mirrors W01.P01.S05 pattern; currently catches only ClassificationError and EnvelopeVersionError but raw ValidationError propagates without typed drift signal; `src/aeat/domain/transactions/_repository.py`.
- [ ] `W09.P41.S215` - replace four dict[str, object] return types on ledger_transaction_payload ledger_transaction_review_payload ledger_transaction_result_payload ledger_transaction_tracking_payload with typed pydantic models; `aeat-architecture-boundaries forbids bare dict at CLI emit boundary; lines 1024 1055 1064 1075 of application ledger _actions.py; `src/aeat/application/ledger/_actions.py`.
- [ ] `W09.P41.S216` - add test coverage for _id_resolution.py 95 LOC module; `currently has no dedicated test file; identify callers and write test_id_resolution.py; `src/aeat/application/ledger/_id_resolution.py`.
- [x] `W09.P41.S217` - verify transaction_catalogue_object_id at application ledger _actions.py line 2607 has callers and test coverage; `potentially orphan internal helper; `src/aeat/application/ledger/_actions.py`.
- [x] `W09.P41.S240` - convention note FU-W04-A: commit d8bec8bd9 co-landed multiple Steps plus exec records plus new test files plus __init__.py changes in a single commit; `future executors should land Step content separately from exec records and from __init__ changes; documentation-only no code change; `.vaultspec/`.
- [x] `W09.P41.S241` - FU-W05-A multi-step co-landing convention note from Wave-5 audit; `commit 03be9b6f4 bundled exec records and step closures; same pattern as FU-W04-A; documentation-only no code change; `.vaultspec/`.
- [x] `W09.P41.S242` - FU-W02-A multi-step co-landing convention note from Wave-2 audit; `commit 30065a92e S38-S42; documentation-only no code change; `.vaultspec/`.
- [x] `W09.P41.S243` - FU-W02-B multi-step co-landing convention note from Wave-2 audit; `commit acea52801 S43+S44+S46; documentation-only no code change; `.vaultspec/`.
- [x] `W09.P41.S244` - FU-W02-C MUST-FIX rewrite test_legal_entity_can_create_modelo_202_work_unit with isolated_runtime_profile fixture; `currently uses monkeypatch AEAT_SECRET_STORE_BACKEND=unsecured to work around the storage regression S209; once S209 lands the unsecured workaround in this test must be removed; blocks Wave-2 quality-gate sign-off; `src/aeat/entrypoints/cli/test_modelo_202_modality.py`.
- [x] `W09.P41.S245` - FU-W07-A multi-step co-landing convention note from Wave-7 review of 01ac9d698 S113+S114; `documentation-only; `.vaultspec/`.
- [x] `W09.P41.S250` - FU-W07-C add age_at DSL operator so casillas 0513/0515 can auto-derive age supplements from renta_taxpayer.birth_date without manual operator input; `UX enhancement closing the silent-zero footgun for >=65 personas who forget to supply the supplement amount; `src/aeat/domain/calculations/registry/`.
- [ ] `W09.P41.S251` - FU-S115-CAT investigate Cataluña 2024 autonomic tarifa discrepancy; `reviewer reconstruction gives 4522.78 EUR for base 35400 but S115/S249 oracle values use 4650.03; either the bracket table is wrong in S115 or there is a complementary tariff source from Orden HAC 2024 Cataluña not yet ingested; ground against AEAT oracle replay before adjusting; `src/aeat/_data/registry/aeat/modelos/100/revisions/2024/`.
- [x] `W09.P41.S252` - S209 BATCH 1 migrate Category A no-active-profile tests to isolated_profile_storage_root: test_profile_create_taxpayer_type_paths test_profile_incn_new_entity_paths test_cold_start_no_profile test_repair_bootstrap_exempt test_fast_path_no_state; `drop AEAT_SECRET_STORE_BACKEND=unsecured and AEAT_ALLOW_UNENCRYPTED monkeypatches; replace with isolated_profile_storage_root fixture; depends on S208; `src/aeat/entrypoints/cli/`.
- [x] `W09.P41.S253` - S209 BATCH 2 migrate Category B active-profile tests to isolated_runtime_profile: test_apex_workflow_verification test_audit_remediation test_cli_surface test_command_suggestions test_modelo_202_modality test_modelo_discovery_defects test_modelo_period_consistency test_modelo_source_mesh_calculate test_modelo_work_applicability_guard test_modelo_work_ux test_profile_output_language test_session_lifecycle_roundtrip; `replace _isolated_backend fixture with runtime_profile fixture using isolated_runtime_profile context manager; CliRunner invocations remain unchanged; `src/aeat/entrypoints/cli/`.
- [x] `W09.P41.S254` - S209 BATCH 3 mixed-fixture triage for test_profile_lifecycle_verbs test_root_grammar_invariants test_root_help_shape; `split create-path tests from active-session tests across test classes or parametrised fixtures; some functions may need isolated_profile_storage_root other functions need isolated_runtime_profile; `src/aeat/entrypoints/cli/`.
- [ ] `W09.P41.S255` - follow-on to W08.P35.S140 sweep: convert 120 hardcoded f-string error raises across 43 application files identified by the Haiku discovery sweep; `full file list and operator-facing subset filed in S140 Step Record; batch by surface (modelo registry storage etc) per locale CLI rule scaffold-then-fill; mechanical work; `src/aeat/application/`.
- [x] `W09.P41.S256` - FU-W07-D surface legal_refs and source_refs on projected M100 casilla values in modelo project verb output payload; `calculation-grounding rule requires every casilla observation to carry its provenance; `src/aeat/entrypoints/cli/_modelo.py`.
- [ ] `W09.P41.S257` - FU-W07-E hexagonal violation in modelo project CLI verb: calculate_registry_snapshot imported from domain.calculations.registry directly at the CLI layer; `extract snapshot acquisition + engine call into a thin application.modelo service function and have the verb call only that service; `src/aeat/entrypoints/cli/_modelo.py`.
- [x] `W09.P41.S258` - FU-W07-F document or test that resources().modelos.authority and _service()._authority yield identical RegistrySnapshots; `the modelo project verb test asserts via two distinct paths but the equivalence is currently implicit; `src/aeat/application/modelo/`.
- [x] `W09.P41.S259` - FU-W07-G S118 + S118-fix co-landing convention note: 604bf217d and f4108869d both touch the S118 scope without an intervening Step record; `documentation-only note for W09; `.vaultspec/`.
- [x] `W09.P41.S261` - FU-W08-C drop unsecured-backend monkeypatches from test_output_language_parity _isolated_state fixture; `--help tests reach no storage layer so no replacement fixture needed; `src/aeat/entrypoints/cli/test_output_language_parity.py`.
- [x] `W09.P41.S262` - FU-W08-D broader --output-language surface sweep: enumerate CLI commands not yet covered by S144 test and assert coverage or document deliberate exclusion; `src/aeat/entrypoints/cli/test_output_language_parity.py`.
- [x] `W09.P41.S263` - FU-W08-A coordination incident note: coder1 and coder2 raced on W08.P36 S141-S144 producing duplicate commit pairs (03016c382/dcc774795 vs 925d8fb0f/02813c853) before coder2 was redirected to Task #72; `establish a task-claim protocol so the same Step cannot be picked off the shared list by two agents simultaneously; `.vaultspec/`.
- [x] `W09.P41.S264` - FU-W08-B remove redundant _activate_subcommand_output_language wrapper in src/aeat/entrypoints/cli/_config/__init__.py; `it is now a one-line shim around the shared helper after the W08.P36 promotion landed; collapse to direct calls; `src/aeat/entrypoints/cli/_config/__init__.py`.
- [x] `W09.P41.S265` - FU-W08-C drop unsecured-backend AEAT_SECRET_STORE_BACKEND=unsecured and AEAT_ALLOW_UNENCRYPTED=1 monkeypatches from _isolated_state autouse fixture in test_output_language_parity.py; `--help never reaches storage so these env-vars serve no purpose; `src/aeat/entrypoints/cli/test_output_language_parity.py`.
- [x] `W09.P41.S266` - FU-W08-D broader --output-language surface sweep beyond the 10 commands covered by S144 regression test; `identify every Typer command across the CLI and confirm flag presence; expand the test to enforce parity over the full set; `src/aeat/entrypoints/cli/`.
- [x] `W09.P41.S267` - FU-S208-A verify all isolated_profile_storage_root callers pass with file-backend change and document aeat_dev_test_database_password CI dependency in secure_sql.py docstring; `src/aeat/tests/secure_sql.py`.
- [ ] `W09.P41.S268` - FU-W10-A extract HAC/242/2025 art-8 text into corpus HTML and add required_text to orden-hac-242-2025:art-8 entry in irpf.toml; `src/aeat/_data/registry/aeat/legal/irpf.toml`.
- [ ] `W09.P41.S269` - FU-W10-B oracle-verify M202 2025-2P and 2025-3P closing dates against AEAT calendar and correct if needed; `src/aeat/_data/registry/aeat/modelos/202/revisions/2025-y-siguientes/deadline_windows/`.
- [x] `W09.P41.S270` - FU-W09-A S267 verify CI sets AEAT_DEV_TEST_DATABASE_PASSWORD environment variable; `the cb51d03e7 commit changed isolated_profile_storage_root from EphemeralMasterKeyProvider to file backend + aeat_dev_test_database_password; without the env-var 8+ existing callers (test_operator test_apex_workflow_verification test_config_reset test_diagnostics test_profile_repository) will fail at passphrase resolution; `.github/workflows/`.
- [ ] `W09.P41.S271` - FU-W09-B S268 corpus gap: HAC/242/2025 art-8 is referenced by the M100 2024 deadline-window registration but the corpus file currently exists only as .json without required_text; `complete the corpus entry with the full BOE text; `.vault/research/`.
- [ ] `W09.P41.S272` - FU-W09-C S269 verify M202 2025-2P and 2025-3P deadline window closing dates against AEAT oracle; `reviewer could not independently confirm dates without sourcing Orden HAC text; `src/aeat/_data/registry/aeat/modelos/202/`.
- [x] `W09.P41.S273` - S253 follow-up: migrate remaining 7 Category B files not covered by cf7775ebe - test_audit_remediation test_command_suggestions test_modelo_202_modality test_modelo_discovery_defects test_modelo_period_consistency test_modelo_work_applicability_guard test_modelo_work_ux; `S253 was marked closed prematurely with only 5 of 12 files migrated; M202 modality file contains S244 must-fix; `src/aeat/entrypoints/cli/`.
- [x] `W09.P41.S274` - side-fix landed in cf7775ebe ledger_transaction_payload counterparty=None coerced to empty string; `resolves Pere persona R7-A defect (ledger list and ledger view CliValidationBoundaryError on CSV-imported transactions with absent currency/counterparty); verify the fix is complete OR if a more typed solution (Optional[str] on LedgerTransactionPayload) is preferable; `src/aeat/application/ledger/_actions.py`.
- [x] `W09.P41.S275` - FU-S274-A centralise counterparty-None coercion into display_counterparty property on TransactionRaw domain model; `retire two identical call-site counterparty or empty-string coercions in ledger actions; `src/aeat/application/ledger/_actions.py`.
- [x] `W09.P41.S276` - FU-S253-A commit message in cf7775ebe says real EphemeralMasterKeyProvider but the helper changed to file backend in cb51d03e7 (S208); `update prior commit message note in step record for accuracy; documentation-only; `.vaultspec/`.
- [ ] `W09.P41.S285` - TAUTOLOGICAL_TEST_SUSPICION sweep S98 follow-up: refactor test_cross_dependency_calculations.py M180 and M190 tests to derive expected values from AEAT workbook or grounded fixture instead of synthetic Decimal hand-computed oracles; `per no-tautological-calculation-tests rule; `src/aeat/domain/calculations/registry/test_cross_dependency_calculations.py`.
- [ ] `W09.P41.S286` - TAUTOLOGICAL_TEST_SUSPICION sweep S98 follow-up: replace monkeypatch.setenv abuse in application/auth/test_operator.py lines 230-260 and 477-521 with Settings override fixture; `AEAT_CERTIFICATE_PATH and AEAT_CLAVE_MOVIL_DNI_NIE injection in application-layer tests should not use env-var monkeypatch; `src/aeat/application/auth/test_operator.py`.
- [ ] `W09.P41.S288` - criterio de caja casilla 62 work split out from S94; `model the Ley 37/1992 art 163 quinquies cash-accounting regime; separate from the intracom axes work; out-of-scope for W05.P24 - surface as W09 or future-wave candidate; `src/aeat/application/aggregation/`.
- [x] `W09.P41.S289` - evaluate access_gate __init__.py env-var read pre-Settings bootstrap; `either lift into Settings (preferred) or write an ADR exception note formalising the early-bootstrap-window exception; `src/aeat/access_gate/__init__.py`.
- [x] `W09.P41.S290` - evaluate core i18n _render.py env-var signature for cache-key invalidation; `either route through Settings or document the cache-coherence rationale in an ADR; `src/aeat/core/i18n/_render.py`.
- [x] `W09.P41.S291` - evaluate core observability _replay.py env-var write for replay scope; `if test-infrastructure-only document inline + restrict via test-only import path; if production-touching lift into Settings; `src/aeat/core/observability/_replay.py`.
- [ ] `W09.P41.S292` - R8-MARC-A surface legal_refs and source_refs in verify and revision CLI outputs; `Marc round-8 round-8 confirmed observations carry provenance in the persisted CalculationRevision but no CLI surface emits them (verification-report view revision casillas formulas describe all lack the columns); add --json flag or sibling subcommand that projects typed observations including legal_refs source_refs formula_id to operator output; `src/aeat/entrypoints/cli/_modelo.py`.
- [ ] `W09.P41.S297` - R8-ROSA-CRITICAL M131 DPA-to-page1 calculation chain not executing under estimacion objetiva modulos regime; `bindings exist for personal asalariado modulo unidades modulo rendimiento neto but motor receives them and returns zeros; formula casilla 04 equals casilla 01 times casilla 02 divided by 100 does not fire; pago fraccionado por modulos cannot be computed; `src/aeat/_data/registry/aeat/modelos/131/`.
- [ ] `W09.P41.S298` - R8-ROSA-CRITICAL M100 missing binding for estimacion objetiva regimen; `only renta-2024-modelo-100-estimacion-directa-es-normal binding visible when profile has irpf.estimation_regime=objetiva; need a rendimiento-neto-modulos binding derived from annual M131 sum for IRPF anual under modulos; `src/aeat/_data/registry/aeat/modelos/100/revisions/2024/bindings/`.
- [x] `W09.P41.S299` - R8-ROSA-CRITICAL M303 does not route to regimen simplificado bindings when profile declares iva.regime=SIMPLIFICADO; `only general regime bindings (iva-repercutido-general-cuota etc) project even though casillas 47-58 for regimen simplificado exist in registry; binding selection must be conditioned on iva.regime; `src/aeat/_data/registry/aeat/modelos/303/`.
- [ ] `W09.P41.S300` - R8-ROSA-A wizard does not ask modulos parameters when profile declares estimacion objetiva regime; `IAE epigraph 972 personal asalariado m2 local kWh anual etc are stable annual values that should be configured in profile not reintroduced in each trimestral calculation; profile schema extension required; `src/aeat/domain/user_profile/_schema.py`.
- [ ] `W09.P41.S302` - R8-ROSA-F add regime incompatibility warnings; `today a profile with irpf.estimation_regime=objetiva can still create M130 (estimacion directa) without any warning and M303 calculated under general regime without flagging the profile declares SIMPLIFICADO; surface a refused/warning when modelo and profile regime conflict; `src/aeat/application/overview/`.
- [x] `W09.P41.S304` - latent circular import between calculations.registry _applicability and deadlines _engine; `introduced by commit 9368c9d46; not actively CLI-blocking (Python resolution order saves it) but fragile and surfaces in test_cross_domain_snapshot_registration; fix via Option A factor TaxpayerModel types to a new leaf module (preferred) OR Option B lazy import guard; `src/aeat/domain/calculations/registry/_applicability.py`.
- [ ] `W09.P41.S307` - R8-NURIA-HIGH M184 atribucion de rentas calculation path missing; `bindings require atribucion_member source which has no CLI entry; sociedad civil and comunidad de bienes contribuyentes cannot file the informative declaration from the CLI; add ledger ordering for entity members (socios) and an atribucion_member source resolver; `src/aeat/_data/registry/aeat/modelos/184/`.
- [ ] `W09.P41.S308` - R8-NURIA-MODERATE bundle export contains cleartext NIF name surnames LOPD risk for gestor sending bundles via email; `encrypt the bundle payload using a recipient-key or a passphrase; preserve the existing v1/v2 schema versioning; `src/aeat/application/user_profile/`.
- [ ] `W09.P41.S309` - R8-NURIA-MODERATE M131 modulos manual entry path missing; `today binding source is ledger only; add CLI path for direct module-data entry on M131 for clients without integrated bookkeeping; supplements W05.P22 income aggregation work which only covers EDS; `src/aeat/entrypoints/cli/_modelo.py`.
- [ ] `W09.P41.S310` - R8-NURIA-LOW orphan bucket cleanup when profile create fails NIF validation; `today failed creates leave bucket directories without manifest.toml that subsequent uniqueness scans then trip over; add rollback transaction in _atomic_create_profile that removes the bucket directory + DEK on validation failure; `src/aeat/application/user_profile/`.
- [ ] `W09.P41.S311` - ambient-index commit discipline violation: peer agent's commit 38d82ce95 absorbed coder1's S296 working tree via git add -A or equivalent; `explicit-pathspec staging is mandatory per the parallel-worktree explicit_path_staging memory; brief subsequent peer dispatches with stronger language; `.vaultspec/`.
- [x] `W09.P41.S313` - remove 6 genuine unused imports flagged by F401: test_certificate_live.py CertificateBackend; `test_verify.py VerifyBrowserContextLike + VerifyBrowserPageLike; test_fx_conversion.py ExchangeRateProvider; test_calendar_applicability_consistency.py derive_modelo_applicability; review _adapters.py TransactionDirection  -  straightforward refactor; `src/aeat/`.
- [ ] `W09.P41.S314` - investigate _legacy_iva_wallet_decision_key at _observations_repository.py line 131  -  only TRUE shim candidate from discovery2 sweep; `verify if non-legacy v2 exists; if active callers remain document the migration path; if dead retire per aeat-architecture-boundaries; `src/aeat/application/calculations/_observations_repository.py`.
- [x] `W09.P41.S318` - fix verification provenance chain  -  separate surface from S210/S211; `add legal_refs and source_refs fields default empty tuple on ModeloVerificationFinding in src/aeat/domain/modelos/_verification_report.py; thread casilla object through _missing_required_casilla_finding call site at _actions.py 2466; thread VerificationPredicateDefinition.legal_refs through _evaluate_verification_predicates for BLOCKING_RULE findings; _verification_report_payload at _modelo.py 2283 emits the fields; regression test with anti-tautology proof mutating TOML legal_refs to empty and asserting the finding follows; `src/aeat/domain/modelos/_verification_report.py`.
- [ ] `W09.P41.S320` - G4 retroactive violation in commit c27f35398  -  added iva_category_help and counterparty_eu_member_state_help keys by hand to en/es/ca/hu.yml without scaffold evidence; `re-scaffold these four keys via python -m aeat.locales scaffold then verify their structural shape matches the canonical pattern; per architect standing-gate enforcement; `src/aeat/locales/`.
- [x] `W09.P41.S321` - FU-W05-E wire effective_eur_amount into amount projection when taxable_base is absent on non-EUR import; `currently exported but unused; non-blocking follow-up from W05.P23 review #122; `src/aeat/domain/transactions/_raw_transaction.py`.
- [x] `W09.P41.S322` - FU-W05-F remove dead shadowed CurrencyNormalizationService construction at test_fx_conversion.py:210; `minor cleanup from W05.P23 review #122; `src/aeat/application/aggregation/test_fx_conversion.py`.
- [ ] `W09.P41.S323` - R9-MANUEL-A SC profile schema lacks socio enumeration; `entity_type=attribution_entity stored as generic legal entity with no fields for nombre de socios percentages NIFs forma juridica; extend UserProfileSchema with attribution_entity-specific section (socios: tuple[SocioEntry, ...] with nif name share_pct fields); required precondition for M184 calculation to work end-to-end; `src/aeat/domain/user_profile/_schema.py`.
- [ ] `W09.P41.S324` - R9-MANUEL-B add cross-profile linkage SC to socio M100; `today base atribuida from M184 does not flow automatically to a member socio personal M100 declaration; socio must manually re-enter the attributed share; design a binding source attribution_received that resolves the share from a known SC profile in the same workspace OR document the manual workflow with explicit CLI prompts; `src/aeat/application/modelo/_profile_binding.py`.
- [x] `W09.P41.S326` - FU-S306-A annotate all_calendars list as list[dict[str, object]] or carry an inline third-party-boundary comment per aeat-calculation-grounding; `minor non-blocking from #131 review of dd8934c72; `src/aeat/entrypoints/cli/_overview.py`.
- [x] `W09.P41.S327` - FU-S318-A simplify _collect_revision_verification_findings  -  casillas_by_id dict lookup is redundant when casilla is already in scope from the snapshot iteration; `pure cleanup not a regression; `src/aeat/application/modelo/_actions.py`.
- [x] `W09.P41.S334` - FU-S278-B tighten LedgerTransactionReviewPayload.classified_by type from str|None to str; `Transaction.classified_by is non-nullable so the None is unreachable at runtime; type imprecision flagged by architect #136; `src/aeat/application/ledger/_models.py`.
- [ ] `W09.P41.S338` - CRITICAL incident log  -  S278 commit c25b14a54 + c94ed9a38 used HEAD-based reconstruction + restore pattern to isolate from peer WIP per coder1 step record; `functionally equivalent to forbidden git-discipline operations; the correct cross-commit pattern is git commit -- only-my-files with cross-authorship note in message never separation by destructive means; code content stands no rollback (rolling back would itself be destructive); incident is the process not the code; `.vaultspec/`.
- [x] `W09.P41.S339` - FU-S96-A two stale .vault-scratch checkpoint files were swept into the bab2adac8 audit-verdict commit; `pre-existing untracked leftovers staged by git add; not peer WIP but worth a stricter explicit-pathspec discipline in future commits to avoid sweeping unrelated tracked leftovers; `.vaultspec/`.
- [ ] `W09.P41.S341` - R9-ANDREA-S341 ROOT CAUSE CORRECTED  -  M303 TOML already has verification_source set correctly in both revisions and 21 M303 tests pass; `the runtime failure observed by Andrea is NOT a TOML authoring gap; three hypotheses: H1 stale registry snapshot cache H2 programmatically-assembled profile from fixture/helper sets corpus_round_trip_verified=True without verification_source H3 code path with construction default; reproduce the exact aeat app modelo work calculate failure in fresh tmp_path and capture full traceback stack; HOLD until reproduction trace lands; `src/aeat/_data/registry/aeat/modelos/303/`.
- [ ] `W09.P41.S343` - R9-ANDREA-HIGH Article 27 LGT late-filing recargo + intereses de demora computation entirely absent from CLI; `no verb flag or field mentions recargo; presenting M130 2022-1T without computing the Art 27 5/10/15/20 percent staged recargo yields an incomplete autoliquidación; substantial new module needed src/aeat/domain/calculations/recargos/_articulo_27.py with date-of-discovery vs original-plazo computation + verb integration on every modelo work calculate that detects late-filing window; `src/aeat/domain/calculations/recargos/`.
- [ ] `W09.P41.S346` - R9-ANDREA-HIGH add pareja de hecho marital status option (5); `Madrid Cataluña and other CCAA recognise pareja de hecho registered as equivalent to married for IRPF autonómico unidad familiar declaración conjunta; current --taxpayer-marital-status accepts only 1-4 (soltero casado viudo separado) forcing operators to choose incorrectly; `src/aeat/domain/user_profile/_schema.py`.
- [ ] `W09.P41.S347` - R9-ANDREA-MEDIUM overview explain for year clearly past plazo (e.g. M100 2022 in 2026) returns applicable=true with no warning about plazo expiry or prescripción 4-year window; `add an out-of-plazo annotation to explain output when overview calendar would have closed >12 months ago; `src/aeat/application/overview/_explain.py`.
- [ ] `W09.P41.S348` - R9-ANDREA-LOW period token notation inconsistency between ledger preflight (uses 2024Q1) and modelo work create (uses 1T); `the system resolves internally but the operator needs to know which format is accepted where; document or normalize; `src/aeat/entrypoints/cli/`.
- [ ] `W09.P41.S349` - R9-ANDREA-CONTEXT registry caching observed to break under concurrent file writes; `FileNotFoundError for 193.toml and TOML parse error on 036.toml occurred during Andrea persona session due to peer agent writes on shared branch; cache invalidation needs to be by directory-fingerprint not file-singular timestamp; `src/aeat/domain/calculations/registry/_loader.py`.
- [ ] `W09.P41.S351` - FU-S279-A low priority typed LogExtra pydantic model to upgrade Mapping[str, object] annotations in service-layer logging helpers; `service-layer helpers are correctly using Mapping[str, object] today (per architect #141 verdict) but a typed LogExtra would tighten the contract; future W09 improvement; `src/aeat/application/`.
- [x] `W09.P41.S352` - R9-TOMAS-CRITICAL S352 add aeat app modelo iva-wallet seed --filing-year --period --amount --confirm verb that creates IvaCompensationPeriodState status=seeded; `the existing _binding_prefill.py path at line 153 silently skips modelo-303-compensacion-pendiente-anteriores when no prior record exists; option (c) --binding override is BLOCKED (escape from reconciliation invariant) and option (b) auto-zero is DANGEROUS (silent wrong value); option (a) explicit seed verb is the architecturally correct path; emit tr()-gated warning about filing accuracy; investigation step: verify whether the --binding override rejection comes from the engine or a missing CLI registration so the error message can be improved either way; `src/aeat/application/calculations/_iva_wallet.py`.
- [ ] `W09.P41.S354` - R9-TOMAS-HIGH subenumerate domestic_exempt IvaCategory; `today it is one bucket but Art. 20.Uno.26 (artistas plena con prorrata) vs 20.Uno.8 (enseñanza sin prorrata) vs 20.Uno.14 etc have different deduction-right implications; add IvaExemptionArticle discriminator on transactions classified as domestic_exempt OR replace single domestic_exempt with article-tagged variants in IvaCategory enum; `src/aeat/domain/iva/_schema.py`.
- [ ] `W09.P41.S355` - R9-TOMAS-HIGH add Modelo 303 casilla 61 operaciones exentas interiores con derecho a deducción; `informativo section for Art. 20 exenciones interiores; today the registry has casilla 60 (exportaciones) but no 61 (interiores); affects all artistas con exenciones del Art. 20.Uno.26 who lose €X.XXX of operations from M303 reporting; `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/casillas/`.
- [ ] `W09.P41.S357` - R9-TOMAS-HIGH AEAT_LOCAL_STORAGE_ROOT collision silent acceptance; `if a path already has another active profile config profile create silently uses the existing profile (loading live-operator-active vs the requested name) without warning; surface a refusal or warning so operator knows their data did not land where they thought; `src/aeat/adapters/persistence/storage/`.
- [ ] `W09.P41.S359` - R9-TOMAS-MEDIUM professional_income_withholding_ge_70pct profile flag has no validation hook on M130; `operator transitioning from 7% to 15% retención can submit M130 with incorrect retención without warning; cross-check casilla 06 against expected (gross_income × tasa_implícita) range and emit a soft warning if the implied rate diverges from the profile's flag; `src/aeat/application/modelo/`.
- [ ] `W09.P41.S360` - FU-S99-A IvaWalletBalanceReport total_balance includes expired lots; `operator cannot distinguish active vs expired from the single figure; add expired_balance and active_balance fields as future W09 enhancement; `src/aeat/application/calculations/_iva_wallet_balance.py`.
- [ ] `W09.P41.S364` - R9-ROBERTO-HIGH Art. 85 LIRPF imputación de rentas inmobiliarias on vacant property not auto-computed; `casilla 0089 is manual; need formula valor_catastral times (1.1 percent if revisado en últimos 10 años else 2 percent) times dias_vacantes divided by 365; obligation when property is at disposicion del contribuyente (no arrendamiento) for any portion of the year; cross with valor_catastral_revisado_fecha to pick correct rate; `src/aeat/_data/registry/aeat/modelos/100/revisions/2024/casillas/`.
- [ ] `W09.P41.S365` - R9-ROBERTO-MEDIUM Art. 25.3 LIRPF 4-year carry-forward of rendimientos negativos del capital inmobiliario not auto-propagated between years; `today operator must manually transcribe negative result from prior year M100 into casilla 0501; design either an auto-binding profile attribution_received pattern from prior CalculationRevision OR a CLI verb aeat app modelo carry-forward --from 2023 --to 2024 --modelo 100; `src/aeat/application/modelo/`.
- [ ] `W09.P41.S366` - R9-ROBERTO-MEDIUM Modelo 100 revision 2024 only exposes 6 profile bindings while 2025 exposes 44; `same gap Anna persona round-7 surfaced; spouse + family + age bindings missing in 2024 forcing manual casilla entry; backfill 2024 profile bindings to match 2025 coverage shape; `src/aeat/_data/registry/aeat/modelos/100/revisions/2024/bindings/`.
- [x] `W09.P41.S367` - CRITICAL gap discovery1 #149  -  Modelo 721 informativa criptomonedas en el extranjero MISSING from registry; `legally required since 2023 per BOE 2023-01-13; no casilla schema no extraction profile no binding selectors no formulas; create full M721 schema under src/aeat/_data/registry/aeat/modelos/721/ with full casilla and binding coverage; required for any persona with crypto holdings on foreign exchanges greater than 50,000 EUR (Eva round-10 persona blocked here); `src/aeat/_data/registry/aeat/modelos/721/`.
- [ ] `W09.P41.S368` - HIGH gap discovery1 #149  -  Beckham regime (Art. 93 LIRPF impatriados) and Modelo 151 NOT MODELLED; `non-resident expatriate income flat-rate 24/47 percent on Spanish-source only for first 6 years; affects all expatriado executives (David round-10 persona); survey AEAT 2024-2025 guides for full coverage scope; create M151 (informativa de participaciones for impatriados) + special M100 handling for impatriado status + preferential flat-rate tarifa formulas + 6-year window expiry tracking; `src/aeat/_data/registry/aeat/modelos/151/`.
- [ ] `W09.P41.S369` - MEDIUM clarify applicability_conditions Python-vs-TOML split per discovery1 #149; `spot checks show applicability_conditions NOT present in revision.toml files (only deadline_windows + legal_refs + source_refs); cross-check S43 implementation in src/aeat/application/profile and src/aeat/domain/applicability to confirm whether applicability filtering is Python-domain-only or requires TOML schema enhancement; document the canonical layer per the architect's W02.P11 verdict (Python rules canonical Option A); `src/aeat/domain/calculations/registry/`.
- [ ] `W09.P41.S370` - FU-S340-A localise next_action hardcoded English in WorkflowStep.details and CLI tab-delimited command-hint lines if/when the tab-delimited surface gets a broader localisation pass; `consistent with pre-existing pattern across other detail keys; non-blocking W09; `src/aeat/application/workflow/_engine.py`.
- [x] `W09.P41.S371` - M100 casilla 1812 auto-propagation from 1811 (crypto ganancia imputable); `flip 1812 input_kind manual to computed with identity-copy formula for both 2024 and 2025 revisions; add regression tests; `src/aeat/_data/registry/aeat/modelos/100/revisions/`.
- [x] `W09.P41.S372` - add typed --row flag mechanism to work calculate for miembro M184 vinculada M232 operador M349 row types; `share ModelRowCollection base; wire rows to observation resolvers; locale keys es/en/ca/hu; oracle-grounded tests per modelo; `src/aeat/entrypoints/cli/_modelo.py`.
- [x] `W09.P41.S373` - route M303 wallet-seed guidance through tr() to iva-wallet seed verb; `fix obsolete --mode hint in error registry; add iva_wallet_not_seeded locale key; regression + anti-tautology CLI tests; `src/aeat/application/modelo/_actions.py src/aeat/core/errors/registry/_domain.py src/aeat/locales/`.
- [x] `W09.P41.S374` - fix M100 base imponible del ahorro chain - add casilla 0041 as summand in renta-2024/2025-base-imponible-del-ahorro formula; `oracle-grounded regression tests for four confirmed persona shapes (Sergio/Carla/Aitor/Mateo) plus anti-tautology; `src/aeat/_data/registry/aeat/modelos/100/revisions/2024/formulas/0145-renta-2024-base-imponible-del-ahorro.toml src/aeat/_data/registry/aeat/modelos/100/revisions/2025/formulas/0168-renta-2025-base-imponible-del-ahorro.toml src/aeat/domain/calculations/registry/test_modelo_100_ahorro_base_chain.py`.
- [ ] `W09.P41.S379` - FU-S372-M349 land OperadorRow .nif crash fix plus detail_rows schema widening plus regression test exercising the full row materialisation per AEAT M349 diseno de registro; `authorising task 250; `src/aeat/_data/registry/aeat/modelos/349/ + src/aeat/domain/modelos/_row_models.py + src/aeat/entrypoints/cli/test_work_calculate_row_flag.py`.
- [ ] `W09.P41.S380` - author m210-irnr-full-engine ADR scoping IRNR base computation plus tipo gravamen plus Convenio doble imposicion routing plus representante fiscal surface; `cite TRLIRNR Arts 11-13 and the Convenios Espana bibliography; concurrent with task 256 per process rule 246 - subsequent multi-step engine wiring lands in a follow-on L3 sub-plan referenced from a future Step; `.vault/adr/2026-05-27-m210-irnr-full-engine-adr.md`.
- [x] `W09.P41.S387` - scaffold M210 registry skeleton per Phase 1 ADR D2 - revision 2025 directory with manifest TOML declaring tax_domain irnr cadence ad_hoc jurisdiction ES-AEAT calculation_class filing legal_refs TRLIRNR Arts 24-25 source_refs BOE-A-2024-22824 Orden HAC/56/2024; `base casillas for rendimiento_integro gastos_deducibles tipo_renta cuota_integra retencion_practicada cuota_diferencial sufficient for the three testimonial personas without the full diseno-de-registro; `src/aeat/_data/registry/aeat/modelos/210/revisions/2025/`.
- [x] `W09.P41.S388` - author bracket_table parameter m210-tipo-gravamen-2025 keyed on tipo_renta returning 0.24 for general Art 25.1.a 0.19 for ue_residente Art 25.1.f NOT_YET_AUTHORED marker for pension deferred to task 229 0.24 for inmobiliaria deferred to Phase 2 0.19 for ganancia_patrimonial Art 25.1.f extension; `extend _validate_revision_rules.py to accept the new string-keyed bracket_table shape; `src/aeat/_data/registry/aeat/modelos/210/revisions/2025/records/parameters.toml + src/aeat/domain/calculations/registry/_validate_revision_rules.py`.
- [x] `W09.P41.S389` - author m210-convenio-rates parameter keyed on country tipo_renta with Phase 1 seed rows for ES-UK ES-MA ES-AR per the testimonial personas; `wire dispatch in formula composition so profile.convenio_doble_imposicion_country triggers treaty-rate lookup replacing the TRLIRNR baseline; emit BLOCKING ModeloVerificationFinding when country is set but no rate row exists per ADR D2.4; `src/aeat/_data/registry/aeat/modelos/210/revisions/2025/records/parameters.toml + src/aeat/application/modelo/_actions.py`.
- [x] `W09.P41.S401` - patch _resolve_m210_rate helper to proceed to Convenio dispatch when baseline row absent (treat per-row absence as legitimate Phase 1 deferral not coherence fault); `add interest tipo row to m210-tipo-gravamen-2025 baseline at TRLIRNR Art 25.1.a 24 percent (pension stays absent per task 229 corpus-blocking); revise S389c synthetic-snapshot test workarounds to exercise real Convenio-override-from-deferred-baseline path; preserves anti-tautology mutation pattern; unblocks S400 formula-authoring which consumes the helper output; `src/aeat/application/modelo/_actions.py + src/aeat/_data/registry/aeat/modelos/210/revisions/2025/parameters/0001-m210-tipo-gravamen-2025.toml + src/aeat/application/modelo/test_modelo_210_phase1.py`.
- [x] `W09.P41.S400` - author 4 M210 formula TOMLs implementing the TRLIRNR Art 24 base + Art 25 rate composition chain (m210-base-imponible-2025, m210-tipo-gravamen-2025-resolve, m210-cuota-integra-2025, m210-cuota-diferencial-2025) and flip the 4 casillas (base_imponible, tipo_gravamen, cuota_integra, cuota_diferencial) from input_kind=manual to input_kind=computed with their formula references wired; `the formula authoring + casilla flip MUST co-land in one atomic commit because partial state would break registry-load; tipo_gravamen formula reads the m210-tipo-gravamen-2025 baseline parameter and the m210-convenio-rates override parameter via the _resolve_m210_rate dispatch helper per ADR D2.4 override-replaces-baseline contract; Path-B refusal stub stays active until S391 flag flip; `src/aeat/_data/registry/aeat/modelos/210/revisions/2025/formulas/ + src/aeat/_data/registry/aeat/modelos/210/revisions/2025/casillas/0001-casillas.toml`.
- [x] `W09.P41.S390` - wire representante-fiscal verification predicate as the first non-M131 use site of implies_nonzero per dsl-conditional-predicate ADR; `runtime evaluator consults profile.ue_eee_status to skip the predicate for EEA residents documented escape hatch per ADR D2.5; author refusal text via tr with locale keys es en ca hu under application.modelo.findings.representante_fiscal_required namespace; `src/aeat/_data/registry/aeat/modelos/210/revisions/2025/verification_expectations.toml + src/aeat/application/modelo/_actions.py + src/aeat/locales/`.
- [x] `W09.P41.S391` - introduce _M210_ENGINE_LIVE feature flag defaulting False in Settings; `tests set True via fixture override; keep the task 196 Path-B refusal active when the flag is False; gate the engine-live branch in modelo_calculate so non-engine personas still hit the refusal until persona-replay gates pass; `src/aeat/core/settings.py + src/aeat/application/modelo/_actions.py`.
- [ ] `W09.P41.S392` - land five Phase 1 acceptance tests per ADR D6 - Olivia Marbella general 24 percent Khadija Marruecos Convenio override at treaty rate Felipe Argentina no Convenio AR row authored emits BLOCKING finding non-EEA without representante_fiscal_nif emits BLOCKING via implies_nonzero EEA resident without representante_fiscal_nif passes the gate; `anti-tautology proof mutates m210-convenio-rates ES-MA row and asserts cuota diverges from the prior hardcoded test value; `src/aeat/_data/registry/aeat/modelos/210/test_modelo_210_phase1.py`.
- [ ] `W09.P41.S393` - FU-task-198 land Convenio doble imposicion + representante fiscal IRNR surfacing for Olivia round-16; `harmonise representante_fiscal_nif field shape between user_profile schema task 197 partial work and the Phase 1 M210 engine; surface representante-fiscal-required refusal at modelo work create when fiscal_residency=NON_RESIDENT and ue_eee_status is False; `src/aeat/domain/user_profile/_schema.py + src/aeat/entrypoints/cli/_modelo.py`.
- [ ] `W09.P41.S394` - FU-task-225 author Convenio Espana-Marruecos rate rows in m210-convenio-rates per BOE-A-1985 Convenio MA Art 14 intereses 10 percent Art 15 rendimientos personales 24 percent or fuente exenta when Spanish-source under treaty; `183-day advisory already authored under tasks 197 225 confirm advisory text references the M210 routing now that the engine exists; `src/aeat/_data/registry/aeat/modelos/210/revisions/2025/records/parameters.toml + src/aeat/application/user_profile/_advisories.py`.
- [ ] `W09.P41.S395` - FU-task-229 author Art 25.1.b TRLIRNR state-pension special tipo as Phase 1 pension bracket row in m210-tipo-gravamen-2025 replaces the NOT_YET_AUTHORED marker; `rate table per BOE Art 25.1.b 8 percent up to 12000 30 percent above 12000; convenio override path applies as a top layer; Felipe round-26 testimonial coverage; `src/aeat/_data/registry/aeat/modelos/210/revisions/2025/records/parameters.toml`.
- [ ] `W09.P41.S396` - FU-task-230 imputacion de rentas inmobiliarias non-resident vivienda vacia per Art 13.1.h TRLIRNR separate from the Phase 2 inmobiliaria full schema; `Phase 1 scope only needs the imputed-rent formula 1.1 percent valor catastral revisado 2 percent otherwise times occupancy fraction routed through casilla rendimiento_integro with tipo_renta=inmobiliaria; defers full deduction routing to Phase 2 sub-plan; `src/aeat/_data/registry/aeat/modelos/210/revisions/2025/formulas/`.
- [ ] `W09.P41.S397` - M210 Phase 2 engine landing - full diseno-de-registro (~80 casillas across 12 tipo-de-renta variants), full Convenios Espana rate roster (~92 countries), agrupacion-anual per Orden HAC/56/2024, and the inmobiliaria/ganancia/pension branch wirings deferred from Phase 1 per ADR D7; `tracked in the m210-irnr-phase-2-engine L3 sub-plan; concurrent ADRs may be required per substantial-new-modelo work; `.vault/plan/2026-05-27-m210-irnr-phase-2-engine-plan.md`.
- [x] `W09.P41.S399` - S386b precursor to S387 - author irnr.toml legal catalogue with TRLIRNR RDLeg 5/2004 entries (Arts 2, 10, 24, 25.1.a, 25.1.f, 47) backed by BOE-A-2004-4527 consolidated HTML corpus snippet authored under src_aeat__data_corpus_normatives_html_trlirnr-rdleg-5-2004.html; `legal_authority evidence_tier; required_text empty for Phase 1 deferred hygiene; plus aeat-modelo-210-procedure source-ref pointing at the existing orden-hac-56-2024.html corpus file; unblocks S387 casilla authoring; architect-2 owned; `src/aeat/_data/registry/aeat/legal/irnr.toml + src/aeat/_data/corpus/normatives/html/trlirnr-rdleg-5-2004.html`.
- [x] `W09.P41.S402` - S400a precursor: author m210-2025-profile-country-of-fiscal-residence binding declaration so the formula op at S400 can consume the enum binding via ctx.enum_binding_values; `matches the canonical M100 precedent at modelos/100/revisions/2025/bindings/0008-renta-2025-profile-tax-residence-ccaa.toml (source=profile, selector profile_model+field+typed_enum, aggregation op=copy); small 1-file 10-line TOML; unblocks S400 main formula authoring; `src/aeat/_data/registry/aeat/modelos/210/revisions/2025/bindings/0001-bindings.toml`.

### Phase `W09.P42` - twin function merge

active_bucket_id_or_raise and require_active_bucket_id have identical bodies. Merge to one canonical function.

- [x] `W09.P42.S165` - merge active_bucket_id_or_raise and require_active_bucket_id into one canonical function update all call sites; `src/aeat/application/workflow/_models.py`.

### Phase `W09.P43` - side-effect re-export refactor

_language_resolver import for side-effect under private name; replace with explicit register_language_resolver call.

- [x] `W09.P43.S166` - replace side-effect _language_resolver import with explicit register_language_resolver call in known initialiser; `src/aeat/application/user_profile/__init__.py`.

### Phase `W09.P44` - hardcoded preflight binding-source set

_LEDGER_PREFLIGHT_BINDING_SOURCES is hardcoded frozenset replace with registry-sourced derivation.

- [x] `W09.P44.S167` - replace _LEDGER_PREFLIGHT_BINDING_SOURCES hardcoded frozenset with registry-sourced derivation; `src/aeat/application/state_projection.py`.

### Phase `W09.P45` - locale _covered_by_namespace duplication

_covered_by_namespace defined identically in two locale modules extract to one.

- [x] `W09.P45.S168` - extract _covered_by_namespace to one location and import from the other; `src/aeat/locales/`.
- [x] `W09.P45.S203` - fix 5 i18n ORPHAN placeholders surfaced by S32 parity validator; `either supply missing kwargs at tr call sites or remove orphan placeholders from locale; keys: cli.app.ledger.inventory.unknown_movement_kind kind; cli.app.ledger.ratios.no_override_error bucket_id and category; cli.app.ledger.ratios.unknown_category raw; cli.app.modelo.work.resume_invalid_target target; `src/aeat/`.
- [ ] `W09.P45.S204` - fix 27 i18n SURPLUS kwargs surfaced by S32 parity validator; `either add placeholders to locale text or remove dead kwargs from tr call sites; affected keys include application.auth.operator.errors.unreadable_active_profile cli.common.errors.invalid_iso_date cli.common.errors.period_unrecognised cli.diagnostics.summary.* cli.diagnostics.version.* cli.ledger.errors.filter_parse_error cli.operator_surface.errors.contract_not_accepted cli.operator_surface.landing.*; `src/aeat/`.
- [ ] `W09.P45.S219` - R7-002 localise 'No pending filing obligation for this profile' refusal on aeat app modelo work file to es ca hu per profile output_language; `currently English only; `src/aeat/entrypoints/cli/_modelo.py`.
- [ ] `W09.P45.S221` - R7-001 / W01.P01 follow-up surface critical storage errors in profile language when the active-profile pointer is readable even if the DEK is malformed; `today DEK-decryption failure surfaces in English regardless of profile output_language; `src/aeat/`.
- [ ] `W09.P45.S222` - R7-001 / W01.P03 follow-up localise ledger CSV date-parse error inner reason; `today wrapper text is es/ca/hu but the inner 'unsupported date format' string is English raw; `src/aeat/entrypoints/cli/_ledger.py`.
- [ ] `W09.P45.S224` - R7-A fix ledger list and ledger view CliValidationBoundaryError on CSV-imported transactions; `LedgerTransactionPayload currency Field min_length 3 max_length 3 rejects empty or short currency strings; ledger review uses LedgerReviewRow without currency and succeeds; relax currency validation OR default to EUR on CSV import OR provide explicit operator-readable error pointing to the CSV currency column not config repair; `src/aeat/application/ledger/_actions.py`.
- [ ] `W09.P45.S225` - R7-C pre-profile error language; `when active-profile pointer is malformed the language resolver cannot read output_language and defaults to Spanish; on subsequent runs after restore the message appears in Catalan; either hardcode multi-language critical-error rendering OR cache last-known-language outside the profile envelope OR document the inevitable Spanish-fallback in the error suggestion; `src/aeat/`.
- [ ] `W09.P45.S226` - R7-D Pere observation calculation-result casilla labels remain in Spanish even with output-language ca; `investigate whether registry casilla.label fields are localised and whether the CLI emitter consults the active profile language when rendering casilla rows; decide whether to translate labels or document the legal-Spanish convention explicitly to operators; `src/aeat/entrypoints/cli/_modelo.py`.
- [ ] `W09.P45.S229` - R7-INES-3 register --output-language option on overview calendar to parity-match other commands; `currently rejected with No such option --output-language; `src/aeat/entrypoints/cli/_overview.py`.
- [ ] `W09.P45.S231` - R7-INES-5 disambiguate the CLI input-validation refusal message from the stored-data validation refusal message; `a malformed --retencion-observation JSON currently emits the same Catalan-Spanish-text and recommends aeat config repair which is wrong; need a distinct argument-validation message pointing to the expected pydantic field shape; `src/aeat/entrypoints/cli/_errors.py`.
- [x] `W09.P45.S232` - R7-INES-6 register --output-language option on config profile subcommand root for parity with other config subcommands; `src/aeat/entrypoints/cli/_config/__init__.py`.
- [ ] `W09.P45.S234` - R7-ANNA-D3 fix iva.regime defaulting to GENERAL for entity_type=natural_person profiles without actividad_economica; `field should remain unset or marked no_aplica until user opts in; misleading for salaried-only profiles; `src/aeat/application/wizard/`.
- [ ] `W09.P45.S235` - R7-ANNA-D4 expand wizard non-TTY refusal message to list the minimum required flags for one-shot profile creation; `currently only --tax-id NIF mentioned but entity-type irpf-income-categories tax-residence-ccaa are also required; `src/aeat/application/wizard/`.
- [ ] `W09.P45.S236` - R7-ANNA-D5 default modelo work create --revision to the in-force revision for the supplied --year via registry lookup; `today operators must run aeat app modelo describe first to find a valid revision id; reduces friction for the common case while preserving explicit override; `src/aeat/entrypoints/cli/_modelo.py`.
- [ ] `W09.P45.S237` - R7-MARC-D1 ledger classify list view blocked by silent profile-completeness gate; `ledger status review update preflight succeed on same profile; config repair confirms ready; no error message identifies which field triggers the gate; surface the specific gate failure to operator or remove the gate; same defect class as R7-A but on different verbs; `src/aeat/application/ledger/`.
- [ ] `W09.P45.S238` - R7-MARC-D3 modelo bindings list without --year --period flags returns binding ids for an arbitrary revision (often the latest); `copy-paste of those ids into work calculate fails with unknown registry binding ids; either narrow the unfiltered output to the work-unit-current revision OR surface a warning that filtering is needed; `src/aeat/entrypoints/cli/_modelo.py`.
- [ ] `W09.P45.S239` - R7-MARC-D4 ledger import --period rejects 2024-1T 1T 2024/1T and 2024Q1 with Periode no reconegut; `works only when omitted; preflight uses AAAAQN format; align ledger import --period parsing with the canonical period token vocabulary established in W01.P07; `src/aeat/entrypoints/cli/_ledger.py`.
- [x] `W09.P45.S282` - HARDCODED_USER_STRING sweep S98 follow-up: route 2 auth _authenticator.py raises via tr() and remove env-var/class-name leakage; `lines 1210 1213 currently expose AEAT_CERTIFICATE_PATH and AEAT_CERTIFICATE_PASSWORD_SECRET env-var names plus CertificateBundle class name; cite AEAT_LIVE_TESTS_ENABLED safety gate per round-5 audit B-ROSER findings; `src/aeat/adapters/outbound/aeat/auth/_authenticator.py`.
- [ ] `W09.P45.S283` - HARDCODED_USER_STRING sweep S98 follow-up: route 9 BadParameter raises in diagnostics/profile.py via tr() (lines 62 66 68 72 77 98 104 117 127-128 153); `bulk locale-CLI migration; coin keys under diagnostics.profile.errors namespace; `src/aeat/diagnostics/profile.py`.
- [ ] `W09.P45.S284` - HARDCODED_USER_STRING sweep S98 follow-up: route diagnostics/secure_objects.py:42-43 BadParameter via tr(); `plus locales/cli.py lines 38 40 42 44 62 (missing/extra/ok labels + scaffold-updated message) via tr(); plus entrypoints/cli/__init__.py:130 version echo via tr(); plus application/wizard/_commands.py:800-804 profile/status/next tab labels via tr(); `src/aeat/`.
- [ ] `W09.P45.S293` - R8-MARC-B verification finding text drifts to Castellano while CLI interface is Catalan; `missing_required_casilla finding inner text not routed via tr() with profile output_language context; locate verification finding rendering and route the message body via tr(); `src/aeat/application/modelo/_actions.py`.
- [ ] `W09.P45.S294` - R8-MARC-C ledger import --period rejects 2026T1 silently with no suggestion of valid format 2026-Q1; `rejection message should suggest the canonical period token form when bare-shape input fails parsing; previously logged as S239 R7-MARC-D4  -  re-confirmed open in round-8; `src/aeat/entrypoints/cli/_ledger.py`.
- [ ] `W09.P45.S295` - W09 wording follow-up Tier-2 import-collision tr() default text reads 'already taken by a different profile' regardless of fresh_uuid_mode; `misleading in the fresh-copy path; distinguish UUID-collision vs label-collision messages; `src/aeat/entrypoints/cli/_config/__init__.py`.
- [ ] `W09.P45.S303` - R8-ROSA-G when profile create rejects a combination of flags surface the SPECIFIC field that failed validation not a generic La entrada del comando no supero la validacion message; `Rosa hit this with taxation-type 2 plus family-minor-children-in-unit and could not identify which pair conflicted; `src/aeat/entrypoints/cli/_config/__init__.py`.
- [ ] `W09.P45.S312` - FU-W05-D add hu.yml locale key-path fallbacks for the two new W05.P24 IVA classification reject reasons (DOMESTIC_COUNTERPARTY_ON_INTRA_COMMUNITY_TRANSACTION + EU_MEMBER_STATE_ON_EXPORT_TRANSACTION); `architect non-blocking follow-up from Task #115 review; `src/aeat/locales/hu.yml`.
- [x] `W09.P45.S316` - register --output-language on work_list work_status work_history work_revisions work_revision and the bare work_runs which currently has no parameters at all; `per discovery3 #121 CLI completeness audit; S144 parity regression test must catch these but currently doesn't; `src/aeat/entrypoints/cli/_modelo.py`.
- [ ] `W09.P45.S317` - add NEXT_ACTION guidance hints to work_verify work_list work_status work_history success/failure outputs per discovery3 #121; `work_calculate already has this pattern (lines 2082-2093 emit explicit next-step guidance)  -  mirror it across the sibling verbs; `src/aeat/entrypoints/cli/_modelo.py`.
- [ ] `W09.P45.S319` - standardise explicit --json flag across CLI verbs; `today _emit_envelope and _emit handle JSON internally without a visible signature parameter; expose --json explicitly so operators know per-verb whether structured output is available; document the flag in --help text; `src/aeat/entrypoints/cli/`.
- [ ] `W09.P45.S328` - R9-ZSOFIA-A localise weekday shift enum values in overview calendar output; `today raw Spanish sabado/domingo leaks into operator-facing shift= field; render via tr() with locale-mapped day names; `src/aeat/application/overview/`.
- [ ] `W09.P45.S329` - R9-ZSOFIA-B identify and localise commands where --language flag is accepted but has no effect on output; `config profile show config auth status modelo work calculate (closing prose only) confirmed broken; the parity test S144 must catch these as ineffective-flag cases not just absent-flag cases; `src/aeat/entrypoints/cli/`.
- [ ] `W09.P45.S330` - R9-ZSOFIA-C state tokens borrador and verificado_completo leak Spanish in operator-facing context; `when emitted alongside operator prose route via tr() with locale-mapped human-readable label OR document they are technical identifiers and keep raw Spanish but always paired with translated prose; `src/aeat/entrypoints/cli/_modelo.py`.
- [ ] `W09.P45.S331` - R9-ZSOFIA-D Kv format error raw technical English string surfaces during work verify error path; `locate and route via tr() with locale-prose explanation of what KV format is; `src/aeat/entrypoints/cli/_modelo.py`.
- [ ] `W09.P45.S332` - R9-ZSOFIA-E broad --help text globally not hu-localised; `even where parent command supports --language hu the help text remains spanish/english; the --help text emission must consult active locale for option descriptions and section headers; `src/aeat/entrypoints/cli/`.
- [ ] `W09.P45.S333` - R9-ZSOFIA-F inconsistent help-text localisation within a single command  -  overview calendar --help has ONE option (--all-profiles) translated to hu but other options remain english; `either localise all options or none; partial localisation is more confusing than uniform; `src/aeat/entrypoints/cli/_overview.py`.
- [ ] `W09.P45.S356` - R9-TOMAS-HIGH ledger view does not show iva_category for entries; `operator cannot confirm domestic_exempt classification visually; auditor cannot verify all artistic invoices are marked exempt vs zero by mistake; add iva_category column to ledger view and ledger list output (operator-visible via tr() locale label); `src/aeat/entrypoints/cli/_ledger.py`.
- [ ] `W09.P45.S358` - R9-TOMAS-HIGH royalties SGAE guidance gap; `the CLI accepts both actividad_economica and capital_mobiliario classifications for royalty income without explaining the legal distinction (Art. 25.4 LIRPF vs rendimiento de actividad económica habitual); add wizard prompt or ledger classify --help text explaining when to use which; `src/aeat/application/wizard/`.

### Phase `W09.P46` - modelo period-handling site count audit

Project-wide grep for every period-token-handling function coverage matrix converge any survivors of Wave 1.

- [ ] `W09.P46.S169` - project-wide grep for every period-token-handling function produce coverage matrix; `if more than one site survives Wave 1 append Steps to converge; `src/aeat/`.

### Phase `W09.P47` - --verbose flag usage audit

For every CLI command registering --verbose assert it actually consumes the flag in its rendering path.

- [x] `W09.P47.S170` - for every CLI command registering --verbose assert it consumes the flag fix or remove unused declarations; `src/aeat/entrypoints/cli/`.

### Phase `W09.P48` - Sonnet drift verification pass

Dispatch Sonnet drift-verification over every file Wave 9 touched fails loudly on remaining duplication shim or re-export.

- [ ] `W09.P48.S171` - dispatch Sonnet drift-verification agent over every Wave-9 touched file fails loudly on remaining duplication shim or re-export; `src/aeat/`.

### Phase `W09.P49` - Wave-9 review and persona re-run BREAKPOINT

Code-reviewer fresh Haiku swarm over 1400 plus files full round-6 fleet repeated plus new tax shapes consolidate expand plan.

- [ ] `W09.P49.S172` - dispatch vaultspec-code-reviewer against every Wave-9 commit; `.vault/exec/`.
- [ ] `W09.P49.S173` - dispatch fresh Haiku discovery swarm over 1400 plus files for drift surviving Wave 9 append Step per finding; `src/aeat/`.
- [ ] `W09.P49.S174` - re-run full round-6 persona fleet plus new tax shapes sociedad civil comunidad de bienes autonomo objetiva trabajador asalariado pensioner with foreign pension; `.vault/audit/`.
- [x] `W09.P49.S175` - consolidate findings and expand this plan in place; `.vault/plan/2026-05-26-cross-domain-continuity-plan.md`.

## Wave `W10` - registry deadline-window backfill

Eight modelos have zero deadline_windows across all revisions: 100 111 180 232 349 390 entirely; 131 has no revisions; 123 130 200 partial. Backfill each.

### Phase `W10.P50` - Modelo 100 deadline windows for 2020 2021 2022 2024 (round-2 R1 follow-up)

Modelo 100 has six revisions but zero deadline_windows. Register windows where corpus authority exists; document the gaps where it does not.

- [x] `W10.P50.S176` - register Modelo 100 deadline windows for exercise 2020 campana filing 2021 requires corpus authority; `src/aeat/_data/registry/aeat/modelos/100/revisions/2020/deadline_windows/`.
- [x] `W10.P50.S177` - register Modelo 100 deadline windows for exercise 2021; `src/aeat/_data/registry/aeat/modelos/100/revisions/2021/deadline_windows/`.
- [x] `W10.P50.S178` - register Modelo 100 deadline windows for exercise 2022; `src/aeat/_data/registry/aeat/modelos/100/revisions/2022/deadline_windows/`.
- [x] `W10.P50.S179` - register Modelo 100 deadline windows for exercise 2024 currently tracked as task 42 gated on Orden HAC 242-2025 corpus landing; `src/aeat/_data/registry/aeat/modelos/100/revisions/2024/deadline_windows/`.

### Phase `W10.P51` - Modelo 111 deadline windows

Modelo 111 has zero deadline_windows. Register 2025 and 2026 quarterly windows grounded in BOE Orden.

- [x] `W10.P51.S180` - register Modelo 111 deadline windows for 2025 quarters 1T 2T 3T 4T BOE Orden grounding required; `src/aeat/_data/registry/aeat/modelos/111/`.
- [x] `W10.P51.S181` - register Modelo 111 deadline windows for 2026 quarters; `src/aeat/_data/registry/aeat/modelos/111/`.

### Phase `W10.P52` - Modelo 180 deadline windows

Modelo 180 has zero deadline_windows across both revisions. Register annual filing window January for prior year.

- [x] `W10.P52.S182` - register Modelo 180 annual deadline windows filing in January for prior year 2025 and 2026; `src/aeat/_data/registry/aeat/modelos/180/`.

### Phase `W10.P53` - Modelo 232 deadline windows

Modelo 232 has zero deadline_windows across both revisions. Register annual filing window November for prior year.

- [x] `W10.P53.S183` - register Modelo 232 annual deadline windows filing in November for prior year 2025 and 2026; `src/aeat/_data/registry/aeat/modelos/232/`.

### Phase `W10.P54` - Modelo 349 deadline windows

Modelo 349 has zero deadline_windows. Register quarterly and above-threshold monthly windows for 2025 and 2026.

- [x] `W10.P54.S184` - register Modelo 349 quarterly and monthly above-threshold deadline windows for 2025 and 2026; `src/aeat/_data/registry/aeat/modelos/349/`.

### Phase `W10.P55` - Modelo 390 deadline windows

Modelo 390 has zero deadline_windows. Register annual IVA-summary window filing in January for 2025 and 2026.

- [x] `W10.P55.S185` - register Modelo 390 annual deadline windows filing in January for 2025 and 2026; `src/aeat/_data/registry/aeat/modelos/390.toml`.

### Phase `W10.P56` - Modelo 131 revision population

Modelo 131 directory has zero revisions. Decide scope: scaffold a revision or document the exclusion.

- [x] `W10.P56.S186` - decide whether Modelo 131 IRPF objective estimation is in scope; `if yes scaffold a revision with casillas and deadline_windows; if no document exclusion; `src/aeat/_data/registry/aeat/modelos/131/`.

### Phase `W10.P57` - Modelo 200 and 202 corporate calendar completion

Modelo 200 has only 2024 windows no 2025; Modelo 202 has 2025-y-siguientes coordinate with foreign-WIP parallel campaign.

- [x] `W10.P57.S187` - register Modelo 200 deadline windows for 2025 fiscal year filing in July 2026; `src/aeat/_data/registry/aeat/modelos/200/`.
- [x] `W10.P57.S188` - verify foreign-WIP Modelo 202 corporate-calendar work lands cleanly; `coordinate with parallel campaign; `src/aeat/_data/registry/aeat/modelos/202/`.

### Phase `W10.P58` - Wave-10 review and persona re-run BREAKPOINT

Code-reviewer and full persona fleet verify every previously-absent calendar entry now appears.

- [ ] `W10.P58.S189` - dispatch vaultspec-code-reviewer against every Wave-10 commit; `.vault/exec/`.
- [ ] `W10.P58.S190` - re-run round-6 personas verify every previously-absent calendar entry now appears; `.vault/audit/`.
- [ ] `W10.P58.S191` - consolidate findings and expand this plan in place; `.vault/plan/2026-05-26-cross-domain-continuity-plan.md`.

## Wave `W11` - loop integration and open-ended expansion contract

Campaign governance scaffolding. Does not complete in the conventional sense; codifies open-ended self-driven nature of the campaign.

### Phase `W11.P59` - the expansion contract

At every Wave terminus coordinator dispatches code-reviewer fresh persona fleet Haiku drift sweep Sonnet grounding; each terminus produces a new audit document and expands THIS plan in place.

- [ ] `W11.P59.S192` - at every Wave terminus dispatch one code-reviewer pass on all Wave commits one fresh persona fleet of at least five distinct tax shapes one Haiku drift sweep on all files touched in the Wave and Sonnet grounding on any new BLOCKER or MAJOR; `produce exec record; cadence target one Wave terminus per active sprint roughly weekly during execution monthly in maintenance; `.vault/exec/`.
- [ ] `W11.P59.S193` - each Wave terminus produces exactly one new audit document via vaultspec CLI; `records persona findings tiered BLOCKER MAJOR MINOR maps each to plan Step or proposes new; explicitly states whether closed findings regressed; audit documents never modified after initial commit regression evidence goes in next audit; `.vault/audit/`.
- [ ] `W11.P59.S194` - each Wave terminus expands THIS plan in place every new BLOCKER and MAJOR becomes a new Step in the appropriate Wave or a new Wave if scope exceeds capacity; `vault plan check must be re-run after every expansion and pass before terminus declared closed; PM executes all structural edits via vault CLI verbs never hand-edit; `.vault/plan/2026-05-26-cross-domain-continuity-plan.md`.
- [x] `W11.P59.S195` - vault plan check must remain green after every plan expansion and after every Step close; `red blocks next Wave dispatch; green = no broken wiki-links no malformed frontmatter no identifier gaps no orphaned Steps; `.vault/plan/2026-05-26-cross-domain-continuity-plan.md`.
- [ ] `W11.P59.S335` - durable maintenance gate one  -  vault check all CI-equivalent runs on every commit to chore branch; `blocks merge if structural drift surfaces; `.github/workflows/`.
- [ ] `W11.P59.S336` - durable maintenance gate two  -  ledger and storage roundtrip test suite remains in CI; `the S108-S109 S254 S273 work built it; never deprecate without explicit replacement; `.github/workflows/`.
- [ ] `W11.P59.S337` - durable maintenance gate three  -  scheduled quarterly persona re-run of 3+ shapes (not ad-hoc); `catches UX drift tests cannot; produces a checkpoint-review audit document each quarter; `.vault/audit/`.

### Phase `W11.P60` - termination criteria

Campaign terminates only when full persona-fleet pass returns zero BLOCKER zero MAJOR AND full Haiku drift sweep returns zero in-scope drift AND vault check all returns clean of new campaign-introduced findings.

- [ ] `W11.P60.S196` - rolling checkpoint declared when ALL five conditions hold: C1 all BLOCKER findings from most-recent persona round closed or have accepted remediation Step; `C2 no new BLOCKER without accepted Step; C3 in-progress coder tasks committed and architect-reviewed; C4 vault plan check green; C5 vault check all reports no new structural drift; checkpoint is NOT termination  -  cadence pause only; loop resumes on next BLOCKER or scheduled persona round; `.vault/audit/`.
- [ ] `W11.P60.S197` - until a valid checkpoint declaration is on record any claim of campaign complete or done is premature; `after a checkpoint at-rest is valid but finished is not; checkpoint declaration itself is a vault audit document authored by architecture-specialist after verifying C1-C5 in sequence; `.vault/plan/2026-05-26-cross-domain-continuity-plan.md`.

## Wave `W12` - structural debt cleanup

consolidated wave hosting promoted W09.P39 + W09.P41 macro-clusters that were too large for their original phases; typed-boundary bulk and registry validate-helper dedup

### Phase `W12.P61` - typed boundary bulk

promote 38 untyped boundary sites surfaced by discovery2 sweep S97; 14 CLI payload functions + 10 application payload functions + 14 cast() + 3 pydantic Any/object; per architect verdict in dac6b09f7

- [x] `W12.P61.S277` - Annotate merged dict in _import_ledger_transactions as dict[str, Transaction] (or extract upsert_transaction helper); `resolves D3 inconsistency noted in FU-S104-A; `src/aeat/application/user_profile/_bundle.py`.
- [x] `W12.P61.S278` - UNTYPED_BOUNDARY sweep S97 follow-up: replace 14 CLI entrypoint payload functions returning dict[str, object] with typed pydantic models; `sites _modelo.py lines 961 1059 1611 1680 1725 2233; _ledger.py lines 2127 2718; _config __init__ line 2214; _common.py line 227; _app_live.py lines 625 725 882 1153; each should return a domain-typed payload model; `src/aeat/entrypoints/cli/`.
- [x] `W12.P61.S279` - UNTYPED_BOUNDARY sweep S97 follow-up: replace 10 application service payload functions returning dict[str, object] with typed pydantic models; `sites auth _diagnostics.py lines 178 185; auth _acquisition_lock.py line 217; filing _review.py line 408; aggregation _service.py line 105; operator_surface _models.py line 225; ledger _actions.py lines 1024 1055 1064 1075; complements coder1 R7-A side-fix work; `src/aeat/application/`.
- [x] `W12.P61.S280` - UNTYPED_BOUNDARY sweep S97 follow-up: replace 14 cast() type-erasure operations with typed alternatives or document third-party API boundary inline per aeat-calculation-grounding; `sites workflow _adapters.py lines 107 112 141 147 203 204; registry _schema.py lines 1219 1231; registry _loader.py line 104; plus 3 pydantic Any/object field declarations at review _actions.py line 18 schedules.py line 86 workflow _models.py line 408; `src/aeat/`.
- [x] `W12.P61.S350` - UNTYPED_BOUNDARY CLI payload sweep: type 13 remaining payload/row helper functions (work_unit, calculation_revision, result_summary, filing_record, verification_report in _modelo.py; `business_invoice + evidence in _ledger.py; bucket_history_event in _config; portal_row + expedientes_row + verify_row + borrador_row in _app_live.py; aggregate_filing_inputs in _common.py); `src/aeat/entrypoints/cli/`.

### Phase `W12.P62` - registry validate helper dedup

promote 8 W09.P39 validate-helper duplicate steps (S149-S156) into a dedicated phase; one canonical _validate_helpers.py with seven import updates

- [x] `W12.P62.S149` - create _validate_helpers.py with canonical _missing_refs and any other shared validate-helpers; `src/aeat/domain/calculations/registry/_validate_helpers.py`.
- [x] `W12.P62.S150` - delete duplicate _missing_refs from _validate_algorithms.py and import from _validate_helpers; `src/aeat/domain/calculations/registry/_validate_algorithms.py`.
- [x] `W12.P62.S151` - same for _validate_constructs.py; `src/aeat/domain/calculations/registry/_validate_constructs.py`.
- [x] `W12.P62.S152` - same for _validate_dependency_sections.py; `src/aeat/domain/calculations/registry/_validate_dependency_sections.py`.
- [x] `W12.P62.S153` - same for _validate_exports.py; `src/aeat/domain/calculations/registry/_validate_exports.py`.
- [x] `W12.P62.S154` - same for _validate_record_sections.py; `src/aeat/domain/calculations/registry/_validate_record_sections.py`.
- [x] `W12.P62.S155` - same for _validate_revision_sections.py; `src/aeat/domain/calculations/registry/_validate_revision_sections.py`.
- [x] `W12.P62.S156` - same for _validate_surfaces.py; `src/aeat/domain/calculations/registry/_validate_surfaces.py`.

### Phase `W12.P63` - M037 historical corpus exhaustive search

Exhaustive WebFetch search of AEAT Sede and BOE for retired M037 Declaracion censal simplificada historical material; capture any retrieved evidence to corpus; document definitive absence of Diseno de Registro.

- [x] `W12.P63.S375` - WebFetch AEAT Sede DR037 xlsx variants and census pages plus BOE-A-2025-410; `capture suppression order text to corpus; write SEARCH_LOG; DR037 Diseno de Registro confirmed absent; domain invariant intact; `src/aeat/_data/corpus/aeat_official/historical_retired_modelos/modelo_037/`.

### Phase `W12.P65` - source_jurisdiction ledger axis - Spanish-source vs foreign-source classification

Introduce a source_jurisdiction axis on the ledger so IRNR M210 routing, Beckham scope filter under Art. 93 LIRPF, and convenio doble imposicion credit can derive from authoritative ledger evidence. Surfaced by Pedro intracom, Olivia UK landlord, Felipe Argentina pensioner, and Khadija Morocco worker testimonials. Affects approximately 600k IRNR plus Beckham filers. Six ordered Steps cover model add, persistence widen, CLI flag, profile-conditional validation, reclassify verb, ADR plus tests.

- [x] `W12.P65.S381` - add source_jurisdiction str ISO 3166-1 alpha-2 field default None to LedgerTransactionPayload and Transaction domain model preserving existing typed roundtrip; `src/aeat/domain/transactions/_models.py + src/aeat/application/ledger/_models.py`.
- [x] `W12.P65.S382` - widen encrypted-SQL persistence boundary for source_jurisdiction; `author grandfather migration that defaults pre-axis rows to None; preserve SecureObjectRepository typed-roundtrip parity per aeat-roundtrip-discipline; `src/aeat/application/ledger/_repository.py`.
- [x] `W12.P65.S383` - register --source-jurisdiction CC flag on aeat app ledger add accepting ISO 3166-1 alpha-2 with refusal text routed via tr(); `add four locale keys es/en/ca/hu via locale CLI scaffold; `src/aeat/entrypoints/cli/_ledger.py`.
- [x] `W12.P65.S384` - add profile-conditional validation IRNR profile rejects non-ES rows on M210 calculate path per Art 13 TRLIRNR; `Beckham regime filters non-ES from IRPF base per Art 93.5 LIRPF; emit ModeloVerificationFinding with legal_refs threaded per S318 provenance pattern; `src/aeat/application/modelo/_actions.py + src/aeat/application/ledger/_preflight.py`.
- [x] `W12.P65.S385` - author source-jurisdiction-axis ADR concurrent with implementation citing Art 13 TRLIRNR and Art 93.5 LIRPF; `add roundtrip test populating source_jurisdiction with non-default value plus anti-tautology proof mutating the persisted column and asserting ValidationError; `.vault/adr/2026-05-27-source-jurisdiction-axis-adr.md + src/aeat/application/ledger/test_source_jurisdiction_roundtrip.py`.
- [x] `W12.P65.S386` - add aeat app ledger reclassify --source-jurisdiction CC verb for backfilling existing entries supporting --transaction-id and --filter scopes reusing bulk-classify partial-success semantics from W05.P25; `src/aeat/entrypoints/cli/_ledger.py + src/aeat/application/ledger/_actions.py`.

## Wave `W13` - Session-surfaced quantification (lint-zero session)

Quantify gaps surfaced during the 2026-06-03 lint-zero session that did not have a tracked Step before: CLI sub-noun-group parity sweep, line-ending normalisation, peer-WIP collision pattern, and other-modelo dual-helper sweep companion. Each Step bounds further work so peer agents inherit the surface without re-discovering it.

### Phase `W13.P66` - Quantification of session-surfaced gaps

Capture concrete follow-up Steps from items the lint-zero session surfaced but did not (and could not) close in-flight.

- [x] `W13.P66.S403` - Extend test_output_language_parity.py to sweep every CLI sub-noun-group (auth_diagnostics, auth_apoderado, repair, bucket, ratios) — W09.P45.S232 closed the 9 config profile verbs only; `src/aeat/entrypoints/cli/test_output_language_parity.py`.
- [x] `W13.P66.S404` - Add .gitattributes mapping py/yml/md/toml to LF normalisation so peer commits stop introducing CRLF on Windows worktrees; `every session's commit logs were noise-cluttered with 'CRLF will be replaced by LF' warnings; `.gitattributes`.
- [x] `W13.P66.S405` - Sweep aggregation + binding pipelines for other dual-helper duplications similar to S159 business-proportion + S200 decimal-binding-value; `specifically look for ledger_period_for_modelo_readiness vs deadline window converters and any sibling iva/renta proportion lookups; `src/aeat/application/aggregation src/aeat/application/modelo`.
- [x] `W13.P66.S406` - Audit peer-WIP collision protocol — the lint-zero session encountered 3+ peer-WIP collisions on core.errors NoActiveProfileError + diagnostics.py refactor + secure-storage event records; `the abort-on-WIP rule applied but the operator-facing test failure was opaque ('AeatError subclass missing ErrorCode registry entry'); needs a clearer refusal-pattern audit; `.vault/audit/`.
- [x] `W13.P66.S407` - Verify CLI sub-noun-group bucket_app maintenance verbs (browse/search/export/import/rename/delete) for S2150 when BucketMaintenanceService lands; `today only 'history' is mounted under bucket_app; `src/aeat/entrypoints/cli/_config/__init__.py`.
