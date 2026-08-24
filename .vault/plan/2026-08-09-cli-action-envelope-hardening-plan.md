---
tags:
  - '#plan'
  - '#cli-action-envelope-hardening'
date: '2026-08-09'
tier: L3
related:
  - '[[2026-08-09-cli-action-envelope-hardening-adr]]'
  - '[[2026-08-09-cli-action-envelope-hardening-research]]'
  - '[[2026-08-09-cli-action-envelope-hardening-reference]]'
modified: '2026-08-24'
body_hash: 'sha256:a7e74bc8c743ecdf73e94be21cc51c56906214f2caa523533b1f86eae11621e7'
---

<!-- RETIRED: S109, S118, S119 -->

# `cli-action-envelope-hardening` plan

## Steps

## Description

Implement the accepted application-owned precondition verdict and
schema-resolved action-chain architecture. The campaign starts by making its
blast radius executable, then introduces the canonical contract, migrates
complete producer-to-projection slices, and closes only through exact live
identity joins and real negative-recovery-retry observations. The related ADR,
research, and reference authorize every Wave. This VaultSpec lifecycle record
is intentionally not routed through the user-documentation pipeline.

Error-default migration is staged and rehome-first. `S50` preserves the
immutable 612-row preimage while it requires a disposition only for each of the
238 historical non-null keys. The current observed-key set, its
constructor/reference partition, scanner-absent set, and structural fingerprint
multiset are always derived afresh from the current source tree at validation
time. A structural fingerprint identity is
`(path, lexical_owner, role, recovery-ast-v1 normalized AST SHA-256,
identical_site_ordinal)`. Canonical `recovery-ast-v1` JSON includes every
semantic field and their order, excluding coordinates only. The locator
`(line, column, end_line, end_column)` is diagnostic metadata only and never
gates a match or owner binding. The lexical fixed-point resolver accepts
explicit imports, aliases, and re-exports, including only statically enumerable
PEP-562 export maps; it rejects ambiguity and nested-scope leakage, and records
every resolved call context. Acceptance compares the derived exact key and
structural-fingerprint multisets, never a count alone. Every observed key begins
as evidence-only `migration_required` with one open scope-valid current owner
bound by structural identity; a scanner-absent key is only eligible for
`retired_or_unreachable` after absence is proven. Reference-only keys start in
`migration_required` and may become `verified_nonproducer_reference` only after
no emitting, dynamic, or re-export route is proven. The final kinds are
`verified_typed_action`, `verified_terminal_no_recovery`,
`verified_nonproducer_reference`, and `retired_or_unreachable`. Line identity
is rejected in this shared campaign because independent worktree edits can shift
coordinates without changing a producer's semantics, so treating a locator as
identity would create false missing or duplicate evidence. The rehoming ledger
carries immutable provenance, structural identity, diagnostic locators, and
ownership evidence only; it remains policy- and locale-neutral and never carries
action, command, condition, prose, or locale policy. Snapshot discovery totals
are evidence only and never architecture.

Historic shard Steps retain immutable allocation evidence and may retire only
after every allocated historical non-null row has a final disposition. `S51`
through `S57` and `S64` remain open until that closure criterion is met.## Steps

## Wave `W01` - Establish the fixed-point census and live denominator

Create the executable candidate ledger and exact live-surface denominator that every migration and closure claim depends on.

### Phase `W01.P01` - Candidate and adjudication inventory

Build the AST-backed candidate census, fixed-point alias expansion, and disposition contract.

- [x] `W01.P01.S01` - Add an AST-backed census emitting stable candidate records keyed by path, enclosing symbol, role, alias, and action identity; `dev/cli_action_census.py`.
- [x] `W01.P01.S02` - Add fixed-point vocabulary expansion and fail a closing pass that discovers a new semantic cluster; `dev/cli_action_census.py`.
- [x] `W01.P01.S03` - Add the adjudicated disposition model with stale-exclusion detection and symbol-scoped reasons; `dev/cli_action_census_dispositions.py`.
- [x] `W01.P01.S04` - Require every census candidate to carry exactly one current disposition; `src/cadrumo/entrypoints/cli/tests/test_suggestion_command_conformance.py`.
- [x] `W01.P01.S49` - Expand migration Phases through the plan CLI with one exclusive Step per adjudicated producer cluster before execution; `.vault/plan/2026-08-09-cli-action-envelope-hardening-plan.md`.
- [x] `W01.P01.S62` - Reconcile deleted and newly exposed census candidates after schema removal without retaining stale compatibility dispositions; `dev/cli_action_census_dispositions.toml`.

### Phase `W01.P02` - Live surface reconciliation

Join callable leaves to schemas, manifest capabilities, policies, MCP exposure, and explicit exclusions by identity.

- [x] `W01.P02.S05` - Expose live Click leaf identity and complete required-input metadata for action binding validation; `src/cadrumo/entrypoints/mcp/_input_schema.py`.
- [x] `W01.P02.S06` - Build the identity reconciliation across leaves, schemas, manifest declarations, policies, and MCP exposure; `src/cadrumo/application/operator_surface/_manifest.py`.
- [x] `W01.P02.S07` - Prove identity joins for callbacks, aliases, exclusions, and policy-filtered MCP leaves; `src/cadrumo/application/operator_surface/tests/test_contract.py`.

## Wave `W02` - Create the canonical action and precondition contract

Introduce application-owned verdicts and catalogue-backed action references before any producer migration begins.

### Phase `W02.P03` - Application-owned contract

Define strict condition, evidence, action, binding, conditionality, and no-recovery models and their catalogue.

- [x] `W02.P03.S08` - Define immutable action references, bindings, precondition verdicts, evidence, conditionality, and no-recovery records; `src/cadrumo/application/operator_actions/_models.py`.
- [x] `W02.P03.S09` - Define the canonical action catalogue without duplicating application guard predicates; `src/cadrumo/application/operator_actions/_catalogue.py`.
- [x] `W02.P03.S10` - Prove strict action-model validation, catalogue uniqueness, binding sufficiency, and terminal outcomes; `src/cadrumo/application/operator_actions/tests/test_models.py`.

### Phase `W02.P04` - Schema-resolved envelope projection

Resolve typed actions against the live command surface and project them consistently through envelope, manifest, and MCP contracts.

- [x] `W02.P04.S11` - Project resolved typed actions through notices while keeping localized text derived; `src/cadrumo/core/json_contract.py`.
- [x] `W02.P04.S12` - Carry resolved precondition actions in error envelopes and retire default suggestions as authority; `src/cadrumo/core/errors/_registry.py`.
- [x] `W02.P04.S13` - Add manifest action-profile records that reference condition and action identities without predicates; `src/cadrumo/application/operator_surface/_models.py`.
- [x] `W02.P04.S14` - Resolve catalogue actions against live command and input schemas and reject insufficient bindings; `src/cadrumo/application/operator_surface/_manifest.py`.
- [x] `W02.P04.S15` - Use the shared action resolver for MCP action projection; `src/cadrumo/entrypoints/mcp/_input_schema.py`.

## Wave `W03` - Migrate the root profile and write-policy slice

Move the root guard and refusal boundary onto typed verdicts while preserving requested command identity and proving recovery.

### Phase `W03.P05` - Root guard verdicts and boundary transport

Replace root recovery prose, preserve leaf identity through pre-dispatch guards, and prove real profile recovery.

- [x] `W03.P05.S16` - Replace storage write-policy recovery hints with typed failed-condition verdicts; `src/cadrumo/application/storage_write_policy.py`.
- [x] `W03.P05.S17` - Preserve requested live leaf identity before root guards and migrate every profile and taxpayer policy refusal in the shared CLI boundary to typed verdicts; `src/cadrumo/entrypoints/cli/_common.py`.
- [x] `W03.P05.S18` - Carry guarded command identity and verdict through the refusal boundary; `src/cadrumo/entrypoints/cli/_errors.py`.
- [x] `W03.P05.S19` - Prove every storage policy condition identity evidence action status and binding set; `src/cadrumo/application/tests/test_storage_write_policy.py`.
- [x] `W03.P05.S20` - Prove clean-root refusal recovery and retry through real CLI dispatch; `src/cadrumo/entrypoints/cli/tests/test_profile_guard_action_recovery.py`.

## Wave `W04` - Migrate workflow and modelo action chains

Replace persisted and rendered workflow continuations with application-owned typed action records and real recovery journeys.

### Phase `W04.P06` - Persisted workflow continuations

Remove untyped workflow next-action details and string-equality localization.

- [x] `W04.P06.S21` - Delete the permissive persisted workflow-details compatibility shape and replace next-action details with closed typed action and precondition records; `src/cadrumo/application/workflow/_models.py`.
- [x] `W04.P06.S22` - Emit typed verdicts from workflow refusal branches; `src/cadrumo/application/workflow/_engine.py`.
- [x] `W04.P06.S23` - Remove English string-equality recovery matching from work-run rendering; `src/cadrumo/entrypoints/cli/_modelo_work_runs_cli.py`.

### Phase `W04.P07` - Modelo leaf predicates and notices

Migrate calculate, verify, and file preconditions and their CLI projections with sufficient bindings.

- [x] `W04.P07.S24` - Migrate adjudicated modelo work and verification predicates to typed verdicts; `src/cadrumo/application/modelo`.
- [x] `W04.P07.S25` - Replace lifecycle suggestion construction with resolved typed action notices; `src/cadrumo/entrypoints/cli/_modelo_work_lifecycle_cli.py`.
- [x] `W04.P07.S26` - Replace unknown-revision and verification continuations with bound or explicitly conditional actions; `src/cadrumo/entrypoints/cli/_modelo_work_verification_cli.py`.
- [x] `W04.P07.S27` - Prove calculate verify and file negative-recovery-retry journeys; `src/cadrumo/entrypoints/cli/tests/test_modelo_action_recovery.py`.

## Wave `W05` - Migrate remaining action-authority clusters

Retire error-registry defaults and free-form operational guidance by complete producer-to-projection slices.

### Phase `W05.P08` - Error catalogue and exception overrides

Convert registered defaults and exception-level action overrides into catalogue references or explicit no-recovery outcomes.

- [x] `W05.P08.S28` - Delete ErrorCode.default_suggestion and define only the current catalogue-backed error action or explicit no-recovery projection; `src/cadrumo/core/errors/_registry.py`.
- [x] `W05.P08.S29` - Fail when an adjudicated exception-override producer lacks an exclusive migration Step; `dev/cli_action_census_dispositions.py`.
- [x] `W05.P08.S30` - Prove registered error recovery resolves against the live command and input surface; `src/cadrumo/entrypoints/cli/tests/test_error_registry_contract.py`.
- [x] `W05.P08.S50` - Retire the historical default-rehoming mechanism after its taxonomy-only migration evidence has been absorbed, leaving the live action census and disposition join as the sole current closure authority; `dev/quality/cli_action_census.py; dev/quality/cli_action_census_dispositions.py; dev/quality/cli_action_census_dispositions.toml`.
- [x] `W05.P08.S51` - Retire remaining recovery-authority claims from the first application registry shard and prove its ErrorCode tuples are taxonomy-only with zero S51-owned structural or locator impact while historical defaults and dispositions remain exclusively in immutable preimage evidence and later producer migrations and unrelated peer locator refreshes are refused; `src/cadrumo/core/errors/registry/_application_part1.py`.
- [x] `W05.P08.S52` - Prove the second application registry shard is taxonomy-only with no recovery authority, retaining historical recovery only in the S50 ledger and 62 migration_required rows exclusively owned by later producer steps; `src/cadrumo/core/errors/registry/_application_part2.py`.
- [x] `W05.P08.S53` - Prove the first domain registry shard is taxonomy-only with no recovery authority, retaining historical recovery only in the S50 ledger where 44 migration_required rows are exclusively owned by later producer steps and 3 rows are retired_or_unreachable; `src/cadrumo/core/errors/registry/_domain_part1.py`.
- [x] `W05.P08.S54` - Prove the second domain registry shard is taxonomy-only with no recovery authority, retaining historical recovery only in the S50 ledger where 34 migration_required rows are exclusively owned by later producer steps and 5 rows are retired_or_unreachable while preserving the peer-owned M303RegimenSimplificadoEvidenceRequiredError taxonomy row; `src/cadrumo/core/errors/registry/_domain_part2.py`.
- [x] `W05.P08.S55` - Prove the third domain registry shard is taxonomy-only with no recovery authority, retaining historical recovery only in the S50 ledger where three migration_required rows are exclusively owned by later producer steps; `src/cadrumo/core/errors/registry/_domain_part3.py`.
- [x] `W05.P08.S56` - Retire recovery-authority comments from the first adapter registry shard and prove its 59 tuple taxonomy remains canonical, retaining historical recovery only in the S50 ledger where eight migration_required rows are exclusively owned by later producer steps; `src/cadrumo/core/errors/registry/_adapters_part1.py`.
- [x] `W05.P08.S57` - Retire recovery-authority comments from the second adapter registry shard and prove its 63 tuple taxonomy remains canonical, retaining historical recovery only in the S50 ledger where 16 migration_required rows are exclusively owned by later producer steps and 2 rows are retired_or_unreachable; `src/cadrumo/core/errors/registry/_adapters_part2.py`.
- [x] `W05.P08.S63` - Retire CadrumoError suggestion compatibility and classify the two internal bare-root validation carriers explicitly so unmigrated user-facing producers remain loud; `src/cadrumo/core/errors/__init__.py; src/cadrumo/application/filing/_producer_snapshot.py; src/cadrumo/core/_orden_anual_html.py`.
- [x] `W05.P08.S64` - Prove the entrypoint registry shard is taxonomy-only with no recovery authority, retaining its two historical defaults only in the S50 ledger where current fingerprints are exclusively owned by S88, S89, and S114; `src/cadrumo/core/errors/registry/_entrypoints.py`.
- [x] `W05.P08.S65` - After the atomic S33/S89 producer-consumer cutover and every S41, S38, S94, S114, and S117 consumer is proven removed, normalize ancillary core optional-extra and external-constants failures to locale keys and machine facts then delete raw install and repair prose plus install_hint with no application import or compatibility alias; `src/cadrumo/core/_optional_extras.py; src/cadrumo/core/external_constants.py; dev/quality/cli_action_census_dispositions.toml`.
- [x] `W05.P08.S96` - Migrate residual Modelo exception recovery producers and forwarding bridges including M303 profile-status, IVA-composition, and filing-evidence active-profile raw-English refusal producers through the canonical locale-neutral precondition/action contract or explicit terminal/no-recovery dispositions and record _preconditions.py as an upstream cross-feature dependency owned by open casilla-schema W01.P01.S01 for reconciliation after release, and migrate the newly introduced work-review exception and precondition producers under the same residual Modelo typed-action or explicit no-recovery contract; `src/cadrumo/application/modelo/_export.py; src/cadrumo/application/modelo/_profile_readiness_gate.py; src/cadrumo/application/modelo/_projection.py; src/cadrumo/application/modelo/_reconcile.py; src/cadrumo/application/modelo/_work_addressing.py; src/cadrumo/application/modelo/_registry_helpers.py; src/cadrumo/application/modelo/_required_binding_gate.py; src/cadrumo/application/modelo/_workflow_gate.py; src/cadrumo/application/modelo/_result_disposition_resolution.py; src/cadrumo/application/modelo/_work_lifecycle.py; src/cadrumo/application/modelo/_calculation_helpers.py; src/cadrumo/application/modelo/_calculation_actions.py; src/cadrumo/application/modelo/_calculation_preparation.py; src/cadrumo/application/modelo/_m349_ledger_guard.py; src/cadrumo/application/modelo/_calculation_modelo_adjustments.py; src/cadrumo/application/modelo/_verification_cross_period.py; src/cadrumo/application/modelo/_amendment_actions.py; src/cadrumo/application/modelo/_amendment_kind_resolution.py; src/cadrumo/application/modelo/_external_import_actions.py; src/cadrumo/application/modelo/_filed_revision_observation.py; src/cadrumo/application/modelo/_filing_actions.py; src/cadrumo/application/modelo/_local_observation_actions.py; src/cadrumo/application/modelo/_local_observation_spreadsheet.py; src/cadrumo/application/modelo/_selectors.py; src/cadrumo/application/modelo/_semantic_role_resolution.py; src/cadrumo/application/modelo/_art20_advisory.py; src/cadrumo/application/modelo/_art52_advisory.py; src/cadrumo/application/modelo/_autonomic_deduccion_advisory.py; src/cadrumo/application/modelo/_binding_resolution.py; src/cadrumo/application/modelo/_borrador_binding.py; src/cadrumo/application/modelo/_calculate_input.py; src/cadrumo/application/modelo/_dt12_advisory.py; src/cadrumo/application/modelo/_dt12_antiquity_advisory.py; src/cadrumo/application/modelo/_history.py; src/cadrumo/application/modelo/_iva_wallet_gate.py; src/cadrumo/application/modelo/_iva_wallet_seed.py; src/cadrumo/application/modelo/_m036_lifecycle.py; src/cadrumo/application/modelo/_m145_communication_records.py; src/cadrumo/application/modelo/_m210_convenio_lob_advisory.py; src/cadrumo/application/modelo/_prior_domiciliation.py; src/cadrumo/application/modelo/_profile_binding.py; src/cadrumo/application/modelo/_review_package.py; src/cadrumo/application/modelo/_review_package_feedback.py; src/cadrumo/application/modelo/_review_package_recipient_encryption.py; src/cadrumo/application/modelo/_review_package_review_only_workspace.py; src/cadrumo/application/modelo/_review_package_signing.py; src/cadrumo/application/modelo/_taxation_comparison.py; src/cadrumo/application/modelo/_verification_actions.py; src/cadrumo/application/modelo/_revision_persistence.py; src/cadrumo/application/modelo/_action_errors.py; src/cadrumo/application/modelo/_m303_regimen_simplificado_scope.py; src/cadrumo/application/modelo/tests/test_m303_regimen_simplificado_scope.py; src/cadrumo/application/modelo/_m303_filing_evidence.py; src/cadrumo/application/modelo/_work_review.py`.
- [x] `W05.P08.S97` - Migrate workflow exception precondition and continuation producers to typed catalogue/live-input verdicts or explicit terminal/no-recovery dispositions; `src/cadrumo/application/workflow/_models.py; src/cadrumo/application/workflow/_engine.py; src/cadrumo/application/workflow/_profile_bucket_scan.py; src/cadrumo/application/workflow/_deadline_stage.py; src/cadrumo/application/workflow/_resume.py`.
- [x] `W05.P08.S99` - Migrate justificante exception action forwarding through cooperative MRO to the retired-error boundary and canonical typed actions; `src/cadrumo/domain/justificante/_errors.py`.
- [ ] `W05.P08.S100` - Replace the remaining ActiveProfilePointerError authored recovery prose and default with a typed catalogue action or explicit no-recovery outcome; `src/cadrumo/core/errors/__init__.py; src/cadrumo/core/config.py; src/cadrumo/core/errors/tests`.
- [x] `W05.P08.S101` - Migrate application user-profile exception producers to typed catalogue/live-input verdicts or explicit terminal/no-recovery dispositions; `src/cadrumo/application/user_profile/_profile_repository.py; src/cadrumo/application/user_profile/_bundle.py; src/cadrumo/application/user_profile/_bundle_encryption.py; src/cadrumo/application/user_profile/_censo_sync.py; src/cadrumo/application/user_profile/_custody.py; src/cadrumo/application/user_profile/_integrity.py; src/cadrumo/application/user_profile/_login_session.py; src/cadrumo/application/user_profile/_orchestration.py; src/cadrumo/application/user_profile/_registration.py; src/cadrumo/application/user_profile/_repository.py`.
- [x] `W05.P08.S102` - Migrate IVA-compensation exception producers to typed catalogue/live-input verdicts or explicit terminal/no-recovery dispositions; `src/cadrumo/domain/iva_compensation/_carry_forward.py; src/cadrumo/domain/iva_compensation/_reconciliation.py`.
- [x] `W05.P08.S103` - Migrate application export exception producers to typed catalogue/live-input verdicts or explicit terminal/no-recovery dispositions; `src/cadrumo/application/export/_tabular.py`.
- [x] `W05.P08.S104` - Migrate calc-sheets exception producers to typed catalogue/live-input verdicts or explicit terminal/no-recovery dispositions; `src/cadrumo/application/storage/calc_sheets/_engine.py; src/cadrumo/application/storage/calc_sheets/_evidence.py; src/cadrumo/application/storage/calc_sheets/_layout.py; src/cadrumo/application/storage/calc_sheets/_translator.py`.
- [ ] `W05.P08.S105` - Finish the portal exception constructor and taxonomy migration, and adjudicate operator reachability for the remaining invoice and IVA validators; `src/cadrumo/domain/portals/_errors.py; src/cadrumo/domain/portals/_registry.py; src/cadrumo/domain/invoices/_models.py; src/cadrumo/domain/iva/_classification.py; src/cadrumo/domain/iva/_saturation.py`.
- [x] `W05.P08.S106` - Migrate config-reset exception producers to typed catalogue/live-input verdicts or explicit terminal/no-recovery dispositions; `src/cadrumo/application/_config_reset_repository.py; src/cadrumo/application/config_reset.py`.
- [x] `W05.P08.S116` - Replace runtime pkgutil result-schema discovery with one canonical schema-module declaration reconciled bidirectionally to the live command and result-schema surface; `src/cadrumo/entrypoints/cli/_app_contract.py; src/cadrumo/entrypoints/schema_surface.py; src/cadrumo/entrypoints/cli/tests/test_app_contract_resilience.py; src/cadrumo/entrypoints/cli/tests/test_json_schema_conformance.py`.

### Phase `W05.P09` - Diagnostics overview and provisioning

Migrate high-density operational guidance and prove blank-state and readiness recovery.

- [x] `W05.P09.S31` - Migrate overview next-step producers and blank-state advisories to typed actions; `src/cadrumo/application/overview`.
- [x] `W05.P09.S32` - Migrate diagnostic remediation records to resolved actions or explicit no-recovery outcomes; `src/cadrumo/application/diagnostics.py`.
- [x] `W05.P09.S33` - Replace every provisioning free-form detail and remediation record (DependencyStatus, ModelSelection, ContentionSnapshot, UnloadOutcome, PullOutcome, ReadinessOutcome, and RemoveOutcome) with locale-neutral typed failed-condition facts and explicit no-recovery outcomes without inventing actions, preserve the two local-model directions, and hand only the changed typed projection to S89; `src/cadrumo/application/provisioning.py`.
- [x] `W05.P09.S34` - Render overview text and JSON from one typed action projection; `src/cadrumo/entrypoints/cli/_overview.py`.
- [x] `W05.P09.S35` - Create the missing end-to-end negative JSON and text locale and recovery-retry proof for overview and provisioning action or no-recovery journeys, deriving each action against the live schema and rejecting raw command prose; `src/cadrumo/entrypoints/cli/tests/test_overview_provisioning_action_recovery.py`.
- [x] `W05.P09.S66` - Migrate preflight remediation producers to typed conditions and canonical actions; `src/cadrumo/application/preflight.py`.

### Phase `W05.P10` - Remaining census-adjudicated producer clusters

Complete the auth, wizard, ledger, deadline, live, adapter, renderer, and locale slices named by the census.

- [x] `W05.P10.S36` - Replace the remaining authentication diagnostics report command literal with a typed action projection or explicit non-action classification; `src/cadrumo/application/auth/_diagnostics.py; src/cadrumo/application/auth/tests`.
- [ ] `W05.P10.S37` - Migrate wizard status, next-step, and missing-input refusal producers to typed failed-condition verdicts with live input bindings or explicit no-recovery outcomes, and prove profile-create recovery rejection.; `src/cadrumo/application/wizard`.
- [x] `W05.P10.S38` - Consume the S33 typed reader-availability facts at _batch_ingest.py and _llm_classification.py within the exclusive ledger area, retain no MissingOptionalExtraError prose or compatibility bridge, and preserve only explicit typed reader-availability verdicts; `src/cadrumo/application/ledger`.
- [ ] `W05.P10.S39` - Replace the remaining DeadlineRecovery.next_command transport and its overview projection with typed recovery actions; `src/cadrumo/domain/deadlines/_models.py; src/cadrumo/domain/deadlines/_recargo.py; src/cadrumo/domain/deadlines/tests/test_extemporaneidad.py; src/cadrumo/domain/deadlines/tests/test_recargo.py; src/cadrumo/application/overview; src/cadrumo/entrypoints/cli/_overview.py`.
- [ ] `W05.P10.S40` - Migrate the remaining LiveIvaSurfaceTimeoutError producers and boundary projection to typed actions with explicit safety dispositions; `src/cadrumo/application/live/_errors.py; src/cadrumo/application/live/_filed_data_capture.py; src/cadrumo/application/live/_iva_remote_state.py; src/cadrumo/entrypoints/cli/_app_live.py`.
- [x] `W05.P10.S41` - Own every new provisioning and optional-extra renderer key and template in all four locale catalogues, accepting only typed condition facts plus resolved action or no-recovery outcome and never feature identity, package command, or English prose; `src/cadrumo/locales`.
- [ ] `W05.P10.S58` - Migrate AEAT adapter recovery producers with explicit external-system safety dispositions including browser _factory.py optional-extra forwarding with typed machine facts and no raw installation prose; `src/cadrumo/adapters/outbound/aeat`.
- [x] `W05.P10.S59` - Remove stale lazy schema-owner-table claims from the config payload surface while S91 exclusively owns residual Modelo CLI action producers; `src/cadrumo/entrypoints/cli/_config_payloads.py`.
- [x] `W05.P10.S60` - Migrate TUI recovery rendering to the shared resolved action projection; `src/cadrumo/adapters/inbound/tui`.
- [x] `W05.P10.S61` - Migrate shipped agent harness action citations to canonical action identities; `src/cadrumo/_data/agent`.
- [x] `W05.P10.S67` - Migrate inbound censo parse-refusal action producers to typed conditions and canonical actions; `src/cadrumo/adapters/inbound/censo/_parser.py`.
- [ ] `W05.P10.S68` - Migrate Google profile, OAuth, and impersonation refusals to typed recoverable actions or explicit operator-decision and safety outcomes; `src/cadrumo/adapters/outbound/google/_active_profile.py; src/cadrumo/adapters/outbound/google/_oauth_flow.py; src/cadrumo/adapters/outbound/google/_impersonation.py; src/cadrumo/adapters/outbound/google/tests`.
- [ ] `W05.P10.S69` - Migrate outbound storage adapter recovery producers to canonical actions or explicit no-recovery outcomes; `src/cadrumo/adapters/outbound/storage`.
- [ ] `W05.P10.S70` - Migrate persistence adapter recovery producers to current typed actions and delete recovery-hint fields; `src/cadrumo/adapters/persistence`.
- [ ] `W05.P10.S71` - Migrate aggregation recovery producers to typed conditions and canonical actions; `src/cadrumo/application/aggregation`.
- [ ] `W05.P10.S72` - Migrate calculation recovery producers to typed conditions and canonical actions; `src/cadrumo/application/calculations`.
- [x] `W05.P10.S73` - Migrate corpus-search recovery producers to typed conditions and canonical actions; `src/cadrumo/application/corpus_search`.
- [x] `W05.P10.S74` - Migrate evidence-service recovery producers to typed conditions and canonical actions; `src/cadrumo/application/evidence`.
- [ ] `W05.P10.S75` - Migrate filing continuation producers to typed conditions and canonical actions; `src/cadrumo/application/filing`.
- [x] `W05.P10.S76` - Migrate inventory recovery producers to typed conditions and canonical actions; `src/cadrumo/application/inventory`.
- [x] `W05.P10.S77` - Replace operator-output suggestion producers with resolved typed action projections; `src/cadrumo/application/operator_output`.
- [x] `W05.P10.S78` - Migrate residual operator-surface action producers outside the manifest and model owners; `src/cadrumo/application/operator_surface/_contract.py; src/cadrumo/application/operator_surface/_errors.py`.
- [x] `W05.P10.S79` - Migrate portal recovery producers to typed conditions and canonical actions; `src/cadrumo/application/portals`.
- [x] `W05.P10.S80` - Migrate integrity-repair continuation producers to typed conditions and canonical actions; `src/cadrumo/application/repair_integrity.py`.
- [x] `W05.P10.S81` - Migrate review action producers to typed conditions and canonical actions; `src/cadrumo/application/review`.
- [x] `W05.P10.S82` - Migrate storage-management recovery producers to typed conditions and canonical actions; `src/cadrumo/application/storage_management`.
- [x] `W05.P10.S83` - Migrate authorization-domain recovery producers to typed conditions and canonical actions; `src/cadrumo/domain/auth`.
- [ ] `W05.P10.S84` - Migrate calculation-registry recovery producers to typed conditions and canonical actions; `src/cadrumo/domain/calculations`.
- [x] `W05.P10.S85` - Migrate taxpayer-domain recovery producers to typed conditions and canonical actions; `src/cadrumo/domain/contribuyente`.
- [x] `W05.P10.S86` - Replace the remaining transaction-model free-form recovery hints and ledger-category command prose with typed conditions and canonical actions or explicit no-recovery outcomes; `src/cadrumo/domain/transactions/_models.py; src/cadrumo/domain/transactions/tests`.
- [x] `W05.P10.S87` - Migrate user-profile-domain recovery producers to typed conditions and canonical actions; `src/cadrumo/domain/user_profile`.
- [ ] `W05.P10.S88` - Migrate root lazy-import optional-extra placeholders and help to use machine identity with localized rendering and the resolved error envelope alongside residual root live and portal CLI producers with no raw feature or package-command compatibility; `src/cadrumo/entrypoints/cli/__init__.py; src/cadrumo/entrypoints/cli/_log_levels.py; src/cadrumo/entrypoints/cli/_app_diagnostics.py; src/cadrumo/entrypoints/cli/_app_diagnostics_telemetry.py; src/cadrumo/entrypoints/cli/_app_maintenance.py; src/cadrumo/entrypoints/cli/_tty.py; src/cadrumo/entrypoints/cli/_app_live.py; src/cadrumo/entrypoints/cli/_app_live_portals_cli.py`.
- [x] `W05.P10.S89` - Complete the consumer half of the atomic S33/S89 provisioning cutover by replacing config-check and provision payload and renderer free-form detail and remediation forwarding plus raw Google package prose with the exact S33 typed projection and resolved action or no-recovery rendering, never hardcoding command or English text; `src/cadrumo/entrypoints/cli/_config`.
- [ ] `W05.P10.S90` - Migrate ledger CLI action producers and co-located renderers without independently authored command prose, including direct PurchaseInvoiceEvidenceInputError consumer migration in _ledger_llm_cli.py and _ledger_lifecycle_cli.py so S38 reader-unavailability verdicts reach the shared envelope intact.; `src/cadrumo/entrypoints/cli/_ledger.py; src/cadrumo/entrypoints/cli/_ledger_business_invoice_cli.py; src/cadrumo/entrypoints/cli/_ledger_classify_cli.py; src/cadrumo/entrypoints/cli/_ledger_evidence_batch_cli.py; src/cadrumo/entrypoints/cli/_ledger_evidence_cli.py; src/cadrumo/entrypoints/cli/_ledger_evidence_review_cli.py; src/cadrumo/entrypoints/cli/_ledger_import_cli.py; src/cadrumo/entrypoints/cli/_ledger_lifecycle_cli.py; src/cadrumo/entrypoints/cli/_ledger_llm_cli.py; src/cadrumo/entrypoints/cli/_ledger_read_cli.py; src/cadrumo/entrypoints/cli/_ledger_rules_cli.py; src/cadrumo/entrypoints/cli/_ledger_counterparty_cli.py; src/cadrumo/entrypoints/cli/_ledger_ratios_cli.py; src/cadrumo/entrypoints/cli/_ledger_review_cli.py; src/cadrumo/entrypoints/cli/_ledger_support.py`.
- [ ] `W05.P10.S91` - Migrate residual modelo CLI action producers and co-located renderers, including every outbound-payload boundary emitter, and delete suggestion-accepting notice helper arguments; `src/cadrumo/entrypoints/cli/_modelo.py; src/cadrumo/entrypoints/cli/_modelo_aggregate_cli.py; src/cadrumo/entrypoints/cli/_modelo_discovery_cli.py; src/cadrumo/entrypoints/cli/_modelo_export_cli.py; src/cadrumo/entrypoints/cli/_modelo_readiness_cli.py; src/cadrumo/entrypoints/cli/_modelo_rendering.py; src/cadrumo/entrypoints/cli/_modelo_amend_wizard_cli.py; src/cadrumo/entrypoints/cli/_modelo_cli_support.py; src/cadrumo/entrypoints/cli/_modelo_iva_wallet_cli.py; src/cadrumo/entrypoints/cli/_modelo_projection_cli.py; src/cadrumo/entrypoints/cli/_modelo_records_cli.py; src/cadrumo/entrypoints/cli/_modelo_review_package_cli.py; src/cadrumo/entrypoints/cli/_modelo_work_lifecycle_cli.py; src/cadrumo/entrypoints/cli/_modelo_work_revision_cli.py; src/cadrumo/entrypoints/cli/_modelo_work_wizard_cli.py; src/cadrumo/entrypoints/cli/_modelo_work_calculate_cli.py`.
- [x] `W05.P10.S92` - Remove the remaining embedded modelo work-list command prose from overview status rendering and derive any executable guidance from the shared resolved action projection; `src/cadrumo/entrypoints/cli/_overview_rendering.py; src/cadrumo/entrypoints/cli/tests`.
- [ ] `W05.P10.S93` - Migrate residual MCP action producers and transport notices to the shared resolved action projection; `src/cadrumo-harness/src/cadrumo_harness/mcp/_tools.py; src/cadrumo-harness/src/cadrumo_harness/mcp/_transport.py; src/cadrumo-harness/src/cadrumo_harness/mcp/_resources.py`.
- [x] `W05.P10.S94` - Migrate LLM optional-extra wrappers and continuations to preserve machine identities or application-owned typed outcomes, including the src/cadrumo/llm/tests/test_llm_vision_classifier.py consumer proof for S38 reader-unavailability verdicts, with no raw installation prose or compatibility.; `src/cadrumo/llm`.
- [ ] `W05.P10.S98` - Migrate application-registry exception recovery producers and forwarding to the retired-error boundary and canonical typed actions; `src/cadrumo/application/registry/_diff.py; src/cadrumo/application/registry/__init__.py; src/cadrumo/application/registry/_conformance.py; src/cadrumo/application/registry/_corpus.py; src/cadrumo/application/registry/_corpus_manual_helpers.py`.
- [x] `W05.P10.S107` - Migrate bucket-maintenance recovery producers to typed conditions and canonical actions; `src/cadrumo/application/bucket_maintenance/_service.py; src/cadrumo/application/bucket_maintenance/_contracts.py; src/cadrumo/application/bucket_maintenance/tests`.
- [x] `W05.P10.S108` - Migrate application invoice-lifecycle recovery producers to typed conditions and canonical actions; `src/cadrumo/application/invoices/_lifecycle.py`.
- [x] `W05.P10.S110` - Replace the remaining modelo-describe recovery strings in state projection with typed conditions and canonical actions or explicit no-recovery outcomes; `src/cadrumo/application/state_projection.py; src/cadrumo/application/tests`.
- [x] `W05.P10.S111` - Migrate core output-rendering recovery producers to typed conditions and canonical actions; `src/cadrumo/core/output_rendering.py`.
- [x] `W05.P10.S112` - Migrate core topics recovery producers to typed conditions and canonical actions; `src/cadrumo/core/topics/__init__.py`.
- [x] `W05.P10.S113` - Migrate domain-bucket recovery producers to typed conditions and canonical actions; `src/cadrumo/domain/buckets/_errors.py`.
- [x] `W05.P10.S114` - Unify shared CLI callback and terminal emitters around one typed projection mapping MissingOptionalExtraError and malformed aeat.pre303 CoreValidationError to exact machine-fact no-recovery outcomes through the CLI exception-precondition owner with no raw message matching or terminal bypass; `src/cadrumo/application/cli_exception_preconditions.py; src/cadrumo/entrypoints/cli/_common.py; src/cadrumo/entrypoints/cli/_errors.py; src/cadrumo/entrypoints/cli/_terminal_errors.py`.
- [x] `W05.P10.S115` - Migrate the active-session diagnostics recovery producer to typed conditions and canonical action or explicit no-recovery outcome; `src/cadrumo/application/diagnostics.py`.
- [x] `W05.P10.S117` - Replace financial OFX optional-extra forwarding and notice consumers with typed machine facts and explicit no-recovery outcomes preserving capability classification without raw installation prose or wrapper compatibility; `src/cadrumo/adapters/inbound/financial/providers/_ofx.py`.
- [x] `W05.P10.S121` - Migrate Google API transport failures to typed external-system safety outcomes, adjudicating remote not-found recovery only where the caller owns creation; `src/cadrumo/adapters/outbound/google/_api.py; src/cadrumo/adapters/outbound/google/tests`.
- [x] `W05.P10.S122` - Migrate Google Drive and document-resolution network, permission, and conflict refusals to typed safety or operator-review outcomes and classify unreachable validation invariants explicitly; `src/cadrumo/adapters/outbound/google/_document_link_resolver.py; src/cadrumo/adapters/outbound/google/_drive_entries.py; src/cadrumo/adapters/outbound/google/tests`.
- [ ] `W05.P10.S123` - Migrate Google calculation-sheet apply and pull transport and synchronization refusals to typed safety or state-divergence outcomes and classify provider-contract validation invariants explicitly; `src/cadrumo/adapters/outbound/google/_calc_sheets_apply.py; src/cadrumo/adapters/outbound/google/_calc_sheets_pull.py; src/cadrumo/adapters/outbound/google/tests`.

## Wave `W06` - Prove action chains and close honestly

Generate the runtime matrix from production declarations, prove negative-recovery-retry behavior, reach a fixed point, and run the independent honesty review.

### Phase `W06.P11` - Runtime matrix and evaluator migration

Replace scenario-authored expectations with production-derived condition and action coverage.

- [ ] `W06.P11.S42` - Generate the leaf-condition-scenario matrix from live surface and production verdict declarations; `dev/agent_eval/_action_coverage.py [new]; src/cadrumo/application/operator_surface/_manifest.py; src/cadrumo/application/operator_surface/_models.py; src/cadrumo/application/operator_actions`.
- [ ] `W06.P11.S43` - Replace scenario-owned expected actions with observed production condition and action assertions; `dev/agent_eval/_models.py`.
- [ ] `W06.P11.S44` - Dispatch negative cases validate bindings execute safe recovery and retry original leaves; `dev/agent_eval/_runner.py`.
- [ ] `W06.P11.S45` - Enforce the bidirectional declaration and observation join, removing retired error-registry-suggestion test references so only the live canonical citation gate remains.; `dev/tests/test_suggestion_command_conformance.py`.

### Phase `W06.P12` - Fixed-point closure and campaign honesty

Require zero unclassified sites and exact declared-observed reconciliation before
campaign closure. `W06` rejects `migration_required` and ambiguous rehoming
rows, revalidates each final typed-producer resolver or terminal proof, proves
retired absence and reference-only status, and preserves the complete immutable
612-row history.

- [ ] `W06.P12.S46` - Require a complete semantic and mechanical pass with no newly discovered action site or alias; `dev/quality/cli_action_census.py; dev/quality/cli_action_census_dispositions.py; dev/tests/test_cli_action_census.py; dev/tests/test_cli_action_census_dispositions.py`.
- [ ] `W06.P12.S47` - Add a code-only closure gate that rejects unclassified sites, unresolved actions, insufficient bindings, missing proofs, or ungrounded exclusions against the live census and operator surface, without reading plans, execution records, audits, or retired rehoming ledgers; `dev/tests/test_action_coverage_closure.py [new]; dev/quality/cli_action_census_dispositions.toml; src/cadrumo/application/operator_surface/_manifest.py; src/cadrumo/application/operator_actions`.
- [ ] `W06.P12.S48` - Publish the final reconciliation and fresh-context honesty findings; `.vault/audit/2026-08-09-cli-action-envelope-hardening-audit.md`.
- [ ] `W06.P12.S95` - Rule what the recoverable-refusal path tells an autonomous operator now that the dead suggestion instruction is struck, stating both branches rather than either, because the strike was correct and landed while its consequence has no row, and what went missing is narrower than silence since both rules now point at the code and the message which the envelope does emit, so the agent can classify a refusal but cannot be told what to run to fix it, which is neither self-remediating nor undiagnosable, and either the replacement is the action field once the migration has advanced far enough that it is not None for most codes, or the path carries no guidance by design and the honest cost is that an autonomous operator must infer the remedy from the code rather than be handed it, a real reduction and a defensible one that must be recorded as a decision rather than left as an accident; `src/cadrumo-harness/src/cadrumo_harness/_data/agent/rules/cadrumo-operator-envelope-reading.md; src/cadrumo/entrypoints/cli/_errors.py; src/cadrumo/core/errors/_registry.py; src/cadrumo/application/operator_actions`.
- [ ] `W06.P12.S120` - Derive the exact registered-code and authored-message join, then partition the positional-English defect into exclusive owner steps without performing a whole-tree migration in this row; `dev/quality/cli_action_census.py; dev/quality/cli_action_census_dispositions.py; dev/tests/test_cli_action_census.py; dev/tests/test_cli_action_census_dispositions.py; src/cadrumo/core; src/cadrumo/application; src/cadrumo/domain; src/cadrumo/adapters; src/cadrumo/entrypoints`.

## Parallelization

Waves are ordered. Within W01, P01 and P02 may run concurrently after agreeing
on stable candidate and leaf identifiers. Within W02, P03 lands before P04.
W03 is the first complete migration slice and must be green before W04 or W05
begins. Within W04, P06 precedes P07 where modelo consumes persisted workflow
records. Within W05, P08, P09, and P10 may run in parallel with exclusive file
ownership after the latest fixed-point census assigns every candidate to one
slice. W06 begins only after all migration dispositions are closed.

Routine discovery, implementation, and verification are owned by Terra high
agents. Cross-cutting contracts, census machinery, live reconciliation, and
proof-matrix work are owned by Terra xhigh agents. Sol remains architecture
advisor and adjudicates only contract conflicts, evidence sufficiency, and
cross-Wave exceptions.

## Verification

- Feature-scoped RAG, AST, exact-search, and live-surface census completes one
  full iteration without discovering a new alias, producer, transformer,
  renderer, command form, or refusal site.
- Every candidate row has exactly one current disposition and every exclusion
  is keyed by symbol and enclosing function with a grounded reason.
- Every operator-callable leaf joins by identity to its result schema, input
  schema, manifest profile, policy classification, action profile, and declared
  MCP exposure or exclusion.
- Every reachable failed precondition emits a stable condition identity,
  evaluated evidence, and either a resolvable action with sufficient bindings
  or an explicit terminal, safety, or operator-decision outcome.
- Every declared actionable outcome joins to a real observation, and every
  observed actionable outcome joins to one declaration.
- Safe deterministic scenarios pass real negative dispatch, recovery dispatch,
  and retry; external and destructive boundaries carry explicit safety proof.
- Targeted owner tests, import-hygiene gates, strict typing, locale parity, and
  the relevant full CLI/MCP envelope suites pass without mocks, patches, skips,
  xfails, or tautological expected actions.
- A fresh-context Terra xhigh honesty review is persisted and every finding is
  closed or formally deferred with a follow-up reference before S48 is checked.
