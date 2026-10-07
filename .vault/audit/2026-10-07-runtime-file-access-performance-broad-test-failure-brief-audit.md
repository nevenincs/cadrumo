---
tags:
  - '#audit'
  - '#runtime-file-access-performance'
date: '2026-10-07'
modified: '2026-10-07'
body_schema: 'body-v2'
body_hash: 'sha256:e215210fd0981501fbc31369b3fb88f560f9dce58810c503de5d6a17f4b3b8c9'
related:
  - "[[2026-10-07-runtime-file-access-performance-plan]]"
---

# `runtime-file-access-performance` audit: broad unit-test failure brief

## Scope

Requested by the user on 2026-10-07 after a report of more than one hundred failures. Inventory the actual broad unit-test reports, check fresh representative defects, and repair confirmed scoped root causes while the authorized Windows rebuild continues.

Earlier batch: `var/storage/development/.logs/test-runs/2026-10-07/20261007T124327.041872Z-pytest-39812-287949c0/run.log`. Remaining-files batch: `var/storage/development/.logs/test-runs/2026-10-07/20261007T134204.686138Z-pytest-32336-e2b05171/run.log`. Both select unit tests while excluding serial, performance, external-tool, keychain, Windows-only, resident-service and private-ingest cases. The second uses `@.logs/full-unit-remaining-2026-10-07.txt` and continues after collection errors. These are different selections, not a before/after reduction. The 157 and 113 failed case events identify 270 distinct cases; a collection error additionally prevented the generated-export module from running. These counts are test failures, separate from warnings and Vault work-in-progress diagnostics.

## Findings

### failure-census | medium | Large reports span several independent owners

| Area, classified by test path | Earlier batch | Remaining-files batch |
|---|---:|---:|
| Registry/compiler/layout/export | 74 | 43 |
| Modelo/revisions/filing | 19 | 20 |
| Localization/catalogues | 15 | 6 |
| TUI/workbench | 16 | 0 |
| Native/packaging/installation | 7 | 6 |
| Operator contracts/evaluation | 0 | 7 |
| Developer/governance/tools | 16 | 15 |
| Other runtime/adapters/domain | 10 | 16 |
| Total failed cases | 157 | 113 |

These area counts are an inventory, not independent root-cause counts. Parameterized cases and dependent routes amplify a shared defect. The batches cover 77 and 68 failing files respectively. Later recorded passes establish individual repairs; absence of a newer run establishes neither a repair nor a fresh failure.

### saved-revision-json | high | Strict inception union decoding rejected valid saved rendering snapshots

RESOLVED by the scoped correction. Fresh reproduction traced the redacted `CalculationRevisionPersistenceError` to `rendering_snapshot.registry_snapshot.modelo.inception` reference arrays. Its before-validator exposes JSON arrays as Python lists to a strict tagged member. Normalizing through existing `freeze_toml_value` restores the tuple boundary already used by authored TOML and predecessor declarations. Saved bytes, digest checks, reference typing, parent authority and encrypted custody are preserved. Both inception arms failed independently added JSON round-trip tests before the fix; both now pass, while null, scalar and non-string reference shapes remain refused. All 13 originally reported calculation-revision persistence failures pass in `20261007T145129.922409Z-pytest-83660-f4a17da2/run.log`. Seven inception/runtime checks and two representative profile cases also pass in `20261007T145023.702028Z-pytest-11404-1281b752/run.log`.

### operator-family-inventory | medium | Live sign-in observation lacked its mounted family declaration

RESOLVED by enrolling `config sign-in-status` as a read-only custody family in `src/cadrumo/application/operator_surface/contract.py`. Fresh reconciliation refused its missing declaration and missing family accounting, affecting eight reported cases across the batches. All 17 action-coverage, production-assertion and CLI refusal-target checks pass in `20261007T144655.852880Z-pytest-88904-9dc38d62/run.log`. Strict reconciliation remains intact; no exclusion or fallback was added.

### historical-export-collection | medium | Range and first-quarter assumptions blocked the export inventory

RESOLVED by the scoped inventory/frame-selection correction. Fresh collection reproduced `generated tree 341/2005-2015 has no law-selectable coordinate` in `20261007T144727.077164Z-pytest-81464-4e3488d2/run.log`. The historical fallback inspected only explicit selector years, overlooking a closed range wholly below the support floor. Correcting it exposed the second defect: the first declared quarter is not fully covered by the official design. The repair recognizes closed ranges and asks the existing canonical source selector for the first fully covered historical frame. Only a typed no-applicable-design refusal permits considering another coordinate; ambiguous authority, undeclared sources and manifest/source/digest disagreement still fail. Static historical inspection does not expand filing support. Collection succeeds, historical M232/M341 frames are checked, the complete export-tree enrollment check passes and an unsupported source frame still refuses: four passing tests in `20261007T145747.074734Z-pytest-62404-320f6cc2/run.log`. Intermediate failed evidence remains in `20261007T145353.448007Z-pytest-55964-8fcf5edd/run.log`.

### modelo-390-worked-example | high | Annual worked-example calculation still fails its independent oracle

UNRESOLVED. Current `dev/registry/tests/test_m390_annual_manual_worked_example.py::test_m390_annual_manual_worked_example_devengada_deducible_resultado` fails in `20261007T145514.639959Z-pytest-54968-cf74f076/run.log`. The original broad trace reports zero against expected annual devengada 88416.00. The test supplies zero prior-filed-303 reconciliation facts alongside annual ledger observations. Trace their precedence and the compiled revision before changing declarations or the fixture. Do not alter the oracle or financial values merely to pass. This is separate from startup parsing and file-access cost.

### remaining-reported-defects | medium | Other groups need current evidence and owning repairs

Reported groups include inherited/bootstrap supersession and predecessor layouts, detached bridge reproduction, stale form source-state digests, provider/source-kind expectations, export value/type agreement, annual endpoints, missing or mismatched locale facts, TUI contracts, package identity, custody/storage and source-governance checks. A bounded current policy probe finds `afiliado_cotizacion` lacks a source-family declaration; eight source-policy cases originally stop at an unclassified kind. Its family/home and locale explanations need completion against the actual affiliate provider.

Historical assertions alone do not establish whether every other case still fails in this concurrently changing tree. The complete inventory below retains last recorded case status and report owner. It is not a full-suite success claim.

### source-policy-fresh-reproduction | medium | All eight originally reported policy cases still failed before enrollment repair

The complete current source-policy file reproduced eight failures and one pass in `20261007T150216.743274Z-pytest-13416-16ea422a/run.log`. The real affiliate provider supplies a typed member contribution calendar, so the owning policy now declares the same register family and absent product home as other independently supplied registers; the existing precedence ladder still leaves its override policy undecided. After that repair the five policy checks passed while four locale cases revealed missing labels. Eight label/origin leaves were then authored through `python -m dev.locales set-batch` for Spanish, English, Catalan and Hungarian. Verification of the complete nine-test file is pending.

### affiliate-policy-repair-verification | low | All nine source-policy and four-language checks now pass

The complete source-policy file passes in `20261007T150722.083603Z-pytest-41008-03c148e0/run.log`, closing its eight originally reported cases. The same probe deliberately included the separate workbench finding-word checks: seven failures remain there and are not reported as repaired. Six share an AST discovery limitation at `verification_predicates.py:780`, where the producer selects between two literal message keys with a conditional expression that the scanner only accepts as one `ast.Constant`; the seventh expects different M349 human headings. Both need an owning scanner/locale contract repair with existing refusal teeth, rather than ignored failures. The combined result is 20 passed and 7 failed.

### modelo-390-oracle-fixture-repair | low | The original financial assertions pass after supplying the stated rate facts

RESOLVED as stale test input, not a demonstrated product arithmetic defect. The current ledger matcher requires `applied_rate` when a binding declares `applied_rates`; the worked-example helpers omitted it, so the annual observations matched no rate-specific row. Six observation helpers now carry the independently stated 21%, 10% and synthetic 4% rates already described by the fixture and its bundled manual evidence. No production formula, expected total, binding override, delta assertion or tax declaration changed. All six existing worked-example tests pass in `20261007T151204.398781Z-pytest-84860-2b5c7508/run.log`, including the independent 88416.00/68202.00/20214.00 totals and recargo, prorrata and super-reducido deltas. This closes the four originally reported cases in that file.

### current-recorded-status | low | Thirty-four originally failing cases pass after the five scoped repairs

The refreshed 270-case inventory records 39 later passes and 231 last-recorded failures. Thirty-four originally failed cases passed in this workstream after the five shared-root repairs, while five other cases already have later passing evidence. Many remaining FAILED statuses still refer to the original broad batches and are not fresh reproductions. The seven separately reproduced TUI finding-word failures remain open. Configured full format, style, type and locale-data checks pass. Three current import aggregates loaded all 4522 modules, kept all 15 contracts and found zero hard violations, but their before/after source identity guards detected concurrent changes. Their overall verdict is unavailable, not PASS; latest report is 20261007T151810.433463Z-check-import-boundaries-58192-5c0a00ee/artifacts/import-health.json.

### additional-build-gate-failures | medium | Documentation checks independently block the rebuilt full package

The separate native bundle attempt failed its documentation gate after 89 minutes. Its log names differences on 19 pages, including old registry generations, revision IDs, M303 formula provenance and M390 formula_count 19 versus current 26. Four examples also failed to execute: two verification-report examples and the IVA applicability example exited 2, and Modelo 100 verification exited 7 with an operation-still-running refusal. Endpoint readiness/deadline and fixture cleanup refusals also appear in the retained Sphinx traceback. These build-gate failures are additional evidence, not part of the 270-case pytest census. Preserve checks and repair the execution or determinism roots before reviewing targeted canonical golden refreshes. Full failed attempt: build/runtime-file-access/rebuild/build-timing.json; diagnostics: build/windows-x64/user-docs/work/compile.log.

### final-current-import-check | low | The source guard still prevents a valid aggregate

The final current-source retry, 20261007T152817.616073Z-check-import-boundaries-63064-612b3db4/artifacts/import-health.json, again loaded all 4522 modules and kept all 15 contracts with zero hard violations. Concurrent source edits changed its snapshot, so the complete gate remains unavailable. S05 stays open for that required verification; further blind retries would add cost without establishing a stable result. The scoped repair test results and 270-case census remain valid within their stated scopes.

### finding-producer-discovery-and-heading | low | Seven freshly reproduced TUI failures now pass

RESOLVED by bounded test-contract repairs. The producer scanner now enumerates both literal branches of a conditional catalogue key, including nested branches, while retaining refusal for dynamic, missing and non-string keys. Both selected-option zero/nonzero finding messages now enter every-language rendering checks. The published selected M349 layout explicitly binds `op.nif-comunitario` to `modelo.schema.349.form.authored.nif-comunitario.heading`; the enrolled English value is `EU VAT number`. The old expectation used the separate `form.column.op-nif-comunitario.heading` leaf (`NIF of the intra-community trader`) which that layout does not select. Only the targeted expected heading changed. No runtime finding, layout or locale content changed.

All 23 tests in the owning TUI finding-word file pass in `20261007T163049.180959Z-pytest-10044-9f47f02d/run.log`, including the seven previously reproduced failures and five new discovery/refusal checks. The refreshed 492-log inventory records 46 later passes / 224 last-recorded failures among the original 270 cases; 41 formerly failed cases passed after this workstream's seven shared roots and five had other later passing evidence. Many remaining entries still refer to the original reports, so they are not asserted to be current failures. The full current import aggregate is still pending: the latest completed run loaded all 4522 modules and kept all 15 contracts but source changed during the run, including our now-completed test repair. A justified retry runs after finalizing those edits.

### registry-supersession-and-predecessor-reproduction | medium | Eighteen remaining reports reproduce at stale fixture or corpus-dependent boundaries

Fresh bounded run `20261007T163659.842775Z-pytest-81280-c5fcfa28/run.log` reports 16 failures, two setup errors and three passes in `test_inherited_bootstrap_supersession.py` and `test_form_layout_predecessor_layout.py` (292.22 seconds). The first group assumes M131 `2026-3t-4t` and M189 `2024`/`2025` still inherit manual export layouts; current canonical trees already publish generated export authority. The production guard correctly refuses a bootstrap supersession over an existing generated tree before later source-pin assertions, and the fixtures can no longer find their assumed manual ancestor. Ten original cases are affected. Repair these fixtures into explicit scratch pre-publication states while retaining source pins, thin-child invariants and refusal/rollback checks; do not roll back published registry data or weaken generated-authority admission.

The other eight cases bind predecessor behavior to current M390 2026 assets, page labels, placements and extracted text. Their assumptions about predecessor seed kind, continuity pagination, running-head text and casilla positions fail in the current corpus. A scratch regeneration also differs from the committed current layout. This is an unresolved authoring/conformance evidence boundary: inspect the exact selected form/design references and independently grounded current page evidence, then separate immutable predecessor-algorithm fixtures from the live registry's conformance checks. Do not assert these failures prove a startup regression, and do not replace the expected layout wholesale with the current output. No production corpus or test expectation in these two files was altered by this workstream.

### native-test-resource-coordination | low | Additional build-gate failures repaired without changing runtime deadlines

Additional native verification failures are separate from the 270-case pytest census. The backpressure reader fixture depended on child executable startup and unbounded suite-list output; a signalled bounded `Read` fixture now exercises the same framing/send/disconnect loop and retains its original five-second termination bound. Production still supplies `ChildStdout`, with static dispatch and unchanged supervisor logic.

A later manager supervision run failed the heartbeat event assertion and timed out a quit-marker observer. The heartbeat assertion now recognizes both valid trajectories: effects become unknown after confirmed termination, or become unknown first when `TerminationUnconfirmed` is emitted and remain unknown through confirmed termination and Hang restart. The latter sequence is admitted only with its explicit unconfirmed event. The real-process CTest fixture target now runs with `--test-threads=1`, preserving all readiness, drain, termination, case and backoff limits. Serial diagnostic runs passed, and the final owning current-source native gate has passed both `manager.rust` (168.35s) and `manager.supervision` (161.96s). Remaining application and package gates are still active.

The configured full format/style/type checks now pass after final path fixes and concurrent packaging corrections. A stale module-target census was refreshed through `python -m dev.quality.import_load_probe --compile-targets`; the ensuing full import aggregate remains pending, so no whole-tree import PASS is claimed yet.

### current-native-and-repository-verdict | low | All thirteen native checks pass while the stable import verdict is unavailable

The final owning Release native verification passes all 13 CTest checks with current source, including the repaired reader, the coordinated real-process supervision suite, application probes, hostile flags and package integrity. CTest takes 650.56 seconds; its owning recipe takes 1130.925 wall / 856.938 descendant CPU seconds. ZIP creation and fresh extracted-package verification remain active. Configured format, style and current type checks pass.

The last complete import aggregate, `20261007T171255.224352Z-check-import-boundaries-14976-f48cf065/artifacts/import-health.json`, loads all 4524 declared modules, retains all 15 contracts, and finds zero load failures or hard violations. The before/after source identity differs, so its complete verdict remains unavailable after 489.997 seconds. The target metadata is now current through its owning generator, but shared-source changes still prevent a stable result. Do not describe the broad suite or current import gate as green. S05 remains open for that required verification; the completed scoped repairs can be checkpointed independently.

## Recommendations

Fix shared runtime/contract defects first and verify their complete affected group. Continue registry arithmetic, applicability, lineage and export failures through existing registry authoring/conformance owners with source evidence. Treat missing policy/catalogue and packaging/governance enrollments as explicit integration work. Do not silence reports through skips, weakened validation, cache admission or bulk golden updates.

Use bounded current reproductions before a broader rerun. The richer safe event/type/frame inventory is `build/runtime-file-access/rebuild/test-report-triage.json`. Last-recorded PASSED means a later execution passed; last-recorded FAILED often remains the original broad run and requires fresh reproduction. All case report basenames below resolve beneath `var/storage/development/.logs/test-runs/2026-10-07`.

### Recorded case inventory

`dev/acceptance/income_tax/tests/test_cli_journey.py`

- `test_installed_cli_records_a_non_json_refusal_without_retaining_its_diagnostic` — FAILED; last report `20261007T134204.686138Z-pytest-32336-e2b05171`.

`dev/acceptance/income_tax/tests/test_installed_tui_child.py`

- `test_admission_autopilot_transfers_exact_login_before_running_separate_root` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.
- `test_admission_autopilot_refusal_never_runs_workflow_and_closes_login_client` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.

`dev/agent_eval/tests/test_action_coverage.py`

- `test_production_matrix_is_live_surface_resolved_and_keeps_outcome_authority_on_profiles` — PASSED; last report `20261007T144655.852880Z-pytest-88904-9dc38d62`.
- `test_matrix_refuses_a_duplicate_resolved_production_identity` — PASSED; last report `20261007T144655.852880Z-pytest-88904-9dc38d62`.
- `test_matrix_lookup_fails_closed_for_a_nonproduction_identity` — PASSED; last report `20261007T144655.852880Z-pytest-88904-9dc38d62`.

`dev/agent_eval/tests/test_production_action_assertions.py`

- `test_observed_action_assertion_uses_a_live_profile_not_a_scenario_authored_action` — PASSED; last report `20261007T144655.852880Z-pytest-88904-9dc38d62`.
- `test_observed_terminal_assertion_compares_the_explicit_production_outcome` — PASSED; last report `20261007T144655.852880Z-pytest-88904-9dc38d62`.
- `test_observed_action_assertion_rejects_a_real_but_wrong_closed_outcome` — PASSED; last report `20261007T144655.852880Z-pytest-88904-9dc38d62`.
- `test_exit_scenario_and_verdict_carry_production_assertions_not_expected_action_fields` — PASSED; last report `20261007T144655.852880Z-pytest-88904-9dc38d62`.

`dev/ci/tests/test_core_external_constants.py`

- `test_test_suite_aeat_route_literals_are_centralized_or_declared` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.

`dev/ci/tests/test_domain_submission_repository.py`

- `TestListAndIter::test_iter_submissions_skips_unreadable_rows_with_warning` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.

`dev/ci/tests/test_os_keychain_lane_scope.py`

- `test_every_os_keychain_case_lies_inside_the_lane_scope` — FAILED; last report `20261007T134204.686138Z-pytest-32336-e2b05171`.
- `test_the_lane_scope_is_read_from_the_recipe_not_hardcoded` — FAILED; last report `20261007T134204.686138Z-pytest-32336-e2b05171`.

`dev/ci/tests/test_storage_write_containment.py`

- `test_no_filesystem_write_uses_an_uncontrolled_external_root` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.

`dev/corpus/tests/test_extraction_sidecar_freshness.py`

- `test_enrolled_corpus_html_trees_use_canonical_lf_bytes` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.
- `test_every_corpus_pdf_has_a_corpus_text_sidecar` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.

`dev/corpus/tests/test_normatives_pdf_provenance_record.py`

- `test_every_bundled_file_is_classified_exactly_once` — FAILED; last report `20261007T134204.686138Z-pytest-32336-e2b05171`.

`dev/docs/tests/test_cli_tree.py`

- `test_machine_secret_and_profile_authentication_metadata_matches_live_projection` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.

`dev/docs/tests/test_docs_build.py`

- `test_docs_build_directory_contains_only_canonical_html` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.

`dev/identity/tests/test_tax_id_respelling_gate.py`

- `test_no_production_site_open_codes_an_identity_comparison_or_key` — FAILED; last report `20261007T134204.686138Z-pytest-32336-e2b05171`.

`dev/locales/tests/test_audit.py`

- `test_committed_catalogues_pass_production_audit` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.
- `test_committed_catalogues_follow_contextual_product_identity_contract` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.
- `test_committed_catalogues_carry_no_em_dash` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.

`dev/locales/tests/test_dynamic_prefix_registry_coverage.py`

- `test_every_dynamic_prefix_is_registry_covered_or_allowlisted` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.
- `test_declaration_list_families_cover_the_live_producer_vocabularies` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.
- `test_language_override_sites_match_the_sanctioned_inventory` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.

`dev/locales/tests/test_finding_message_facts_are_guaranteed.py`

- `test_the_gate_reaches_the_live_producers` — FAILED; last report `20261007T134204.686138Z-pytest-32336-e2b05171`.
- `test_the_check_bites_when_a_producer_stops_supplying_a_fact` — FAILED; last report `20261007T134204.686138Z-pytest-32336-e2b05171`.
- `test_no_finding_message_renders_an_unsupplied_placeholder` — FAILED; last report `20261007T134204.686138Z-pytest-32336-e2b05171`.

`dev/locales/tests/test_form_layout_heading_exemption.py`

- `test_declared_headings_and_the_shared_vocabulary_are_exempt` — FAILED; last report `20261007T134204.686138Z-pytest-32336-e2b05171`.
- `test_the_committed_catalogues_carry_no_extra_heading_keys` — FAILED; last report `20261007T134204.686138Z-pytest-32336-e2b05171`.

`dev/locales/tests/test_locale_translation_honesty.py`

- `test_modelo_spanish_values_are_authority_source` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.
- `test_casilla_labels_are_translated_not_copied` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.
- `test_no_translated_lineage_leaves_a_row_in_spanish` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.
- `test_every_untranslated_label_is_a_classified_identical_term` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.

`dev/locales/tests/test_modelo_schema_runtime_localization.py`

- `test_every_shipped_modelo_schema_localization_resolves_for_every_output_locale` — FAILED; last report `20261007T134204.686138Z-pytest-32336-e2b05171`.

`dev/locales/tests/test_parity.py`

- `test_codebase_to_locale_parity` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.

`dev/locales/tests/test_shipped_casilla_catalogue.py`

- `test_the_shipped_casilla_catalogue_stores_each_text_once` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.
- `test_every_casilla_label_resolves_in_spanish` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.
- `test_no_composed_segment_is_rendered_two_ways` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.
- `test_no_rendering_stands_for_two_composed_segments` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.

`dev/packaging/tests/test_authority_runtime_boundary.py`

- `test_revision_selection_delegates_year_admission_to_the_shared_catalogue` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.

`dev/packaging/tests/test_build_scratch_reclaim.py`

- `test_sweep_spares_every_live_var_member_however_old` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.

`dev/packaging/tests/test_cadrumo_data_distribution.py`

- `test_companion_wheel_is_under_the_pypi_file_cap` — FAILED; last report `20261007T134204.686138Z-pytest-32336-e2b05171`.

`dev/packaging/tests/test_hashing.py`

- `test_rehomed_text_digest_module_uses_the_canonical_helper[dev.packaging.distribution_evidence_emit]` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.

`dev/packaging/tests/test_native_artifact_identity.py`

- `test_application_probe_receives_extracted_root_and_controls_acceptance[0]` — FAILED; last report `20261007T134204.686138Z-pytest-32336-e2b05171`.
- `test_application_probe_receives_extracted_root_and_controls_acceptance[7]` — FAILED; last report `20261007T134204.686138Z-pytest-32336-e2b05171`.
- `test_application_probe_receives_extracted_root_and_controls_acceptance[10]` — FAILED; last report `20261007T134204.686138Z-pytest-32336-e2b05171`.

`dev/packaging/tests/test_native_docs_staging.py`

- `test_every_language_page_comes_back_from_the_structure_and_its_text` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.

`dev/packaging/tests/test_native_storage_environment_contract.py`

- `test_desktop_defaults_project_canonical_declarations` — FAILED; last report `20261007T134204.686138Z-pytest-32336-e2b05171`.

`dev/packaging/tests/test_release_cohort.py`

- `test_release_builder_identity_is_the_exact_checked_in_cpython_pin` — FAILED; last report `20261007T140944.240561Z-pytest-60792-d3ebf1ad`.

`dev/packaging/tests/test_smoke_core_payload.py`

- `test_core_wheel_contains_every_runtime_member_and_no_split_owned_binary` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.

`dev/packaging/tests/test_tooling_sources_carry_no_invisible_bytes.py`

- `test_every_carriage_return_payload_in_the_tooling_trees_pins_its_newline` — FAILED; last report `20261007T134204.686138Z-pytest-32336-e2b05171`.

`dev/packaging/tests/test_var_scratch_mint_sites_are_registered.py`

- `test_no_var_scratch_name_is_spelled_at_its_call_site` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.

`dev/quality/tests/test_doc_privacy.py`

- `test_no_operator_identifying_tokens_in_the_repository` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.

`dev/quality/tests/test_git_invocations_take_no_optional_locks.py`

- `test_every_git_invoking_module_declines_optional_locks` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.

`dev/quality/tests/test_governed_fact_runtime_reads.py`

- `test_product_runtime_reads_governed_data_only_through_authority_or_named_s80_exception` — FAILED; last report `20261007T134204.686138Z-pytest-32336-e2b05171`.

`dev/quality/tests/test_workspace_doors_are_wholly_wired.py`

- `test_no_workspace_door_is_wired_in_part` — FAILED; last report `20261007T134204.686138Z-pytest-32336-e2b05171`.

`dev/registry/compiler/tests/test_export_field_placement.py`

- `test_a_binding_derived_record_is_judged_on_its_binding_spans_too` — FAILED; last report `20261007T134204.686138Z-pytest-32336-e2b05171`.

`dev/registry/compiler/tests/test_export_layout_reserved_constant.py`

- `test_the_design_prescribed_constant_may_occupy_its_reserved_bytes` — FAILED; last report `20261007T134204.686138Z-pytest-32336-e2b05171`.
- `test_any_other_value_in_the_reserved_bytes_is_refused` — FAILED; last report `20261007T134204.686138Z-pytest-32336-e2b05171`.

`dev/registry/conformance/tests/test_registry_schema_part1.py`

- `test_validator_rejects_invalid_invoice_binding_shapes` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.
- `test_export_fields_can_reference_structured_bindings` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.

`dev/registry/form_layout/tests/test_form_layout_generation.py`

- `test_every_moved_placement_is_acknowledged_and_no_acknowledgement_is_stale` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.
- `test_the_stability_gate_detects_an_unacknowledged_and_a_stale_move` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.

`dev/registry/form_layout/tests/test_form_layout_integrity.py`

- `test_a_changed_literal_scale_requires_regenerating_its_form_companion` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.

`dev/registry/form_layout/tests/test_form_layout_official_headings.py`

- `test_every_quote_heads_its_part_in_the_committed_layout` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.
- `test_a_quote_for_a_part_the_design_already_names_is_refused` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.

`dev/registry/form_layout/tests/test_form_layout_predecessor_layout.py`

- `test_390_2026_keeps_each_continuing_box_where_its_own_form_prints_it` — FAILED; last report `20261007T144030.537469Z-pytest-23544-6ec3d06a`.
- `test_390_2026_is_paginated_like_2025_for_every_box_it_declares` — FAILED; last report `20261007T144030.537469Z-pytest-23544-6ec3d06a`.
- `test_the_form_reader_sets_aside_running_heads_and_arithmetic_captions` — FAILED; last report `20261007T144030.537469Z-pytest-23544-6ec3d06a`.
- `test_a_scratch_copy_of_the_form_reproduces_the_committed_layout` — FAILED; last report `20261007T144030.537469Z-pytest-23544-6ec3d06a`.
- `test_a_box_its_page_no_longer_prints_falls_to_the_numbered_page` — FAILED; last report `20261007T144030.537469Z-pytest-23544-6ec3d06a`.
- `test_a_page_label_printed_on_two_pages_confirms_neither` — FAILED; last report `20261007T144030.537469Z-pytest-23544-6ec3d06a`.
- `test_an_apartado_its_page_no_longer_prints_drops_its_sections` — FAILED; last report `20261007T144030.537469Z-pytest-23544-6ec3d06a`.
- `test_a_revision_with_its_own_record_design_never_follows_its_predecessor` — FAILED; last report `20261007T144030.537469Z-pytest-23544-6ec3d06a`.

`dev/registry/pipeline/tests/test_below_floor_dispositions.py`

- `test_repaired_m232_static_target_needs_no_drift_row_or_runtime_filing_admission` — FAILED; last report `20261007T134204.686138Z-pytest-32336-e2b05171`.

`dev/registry/pipeline/tests/test_delta_target_publication.py`

- `test_an_absent_tree_on_a_delta_target_publishes_and_derives_the_full_copys_references` — FAILED; last report `20261007T134204.686138Z-pytest-32336-e2b05171`.

`dev/registry/pipeline/tests/test_generated_export_inheritance.py`

- `test_static_storage_verification_refuses_a_changed_earlier_ancestor` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.
- `test_real_child_delta_hydrates_to_full_render_and_old_tree_is_exact` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.
- `test_changed_source_pins_baseline_or_layout_refuse_compaction` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.

`dev/registry/pipeline/tests/test_generated_tree_scope_context.py`

- `test_real_123_bootstrap_candidate_uses_validated_shared_role_scope` — FAILED; last report `20261007T134204.686138Z-pytest-32336-e2b05171`.

`dev/registry/pipeline/tests/test_inherited_bootstrap_supersession.py`

- `test_reviewed_inherited_manual_layout_has_unique_source_pinned_ancestor[131-2026-3t-4t-2026-modelo-131-fichero-boe-1-aeat-dr-131-2026-late-b394370ae16d303a3ed7e192ca34ba1ff49dbbbea49e4d2bbe220085cc53600f]` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.
- `test_reviewed_inherited_manual_layout_has_unique_source_pinned_ancestor[189-2024-2023-modelo-189-fichero-2023-0-aeat-dr-189-2023-c493f8d9d927f28211336324cbe17ab7bae7b256d3c563273e01a76834757d6a]` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.
- `test_reviewed_inherited_manual_layout_has_unique_source_pinned_ancestor[189-2025-2023-modelo-189-fichero-2023-0-aeat-dr-189-2023-c493f8d9d927f28211336324cbe17ab7bae7b256d3c563273e01a76834757d6a]` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.
- `test_inherited_layout_refuses_missing_or_wrong_source_pins_and_identity` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.
- `test_inherited_layout_refuses_changed_or_missing_ancestor` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.
- `test_reviewed_candidate_detaches_only_target_and_keeps_ancestor_intact[131-2026-3t-4t-2026-modelo-131-fichero-boe-1-aeat-dr-131-2026-late-b394370ae16d303a3ed7e192ca34ba1ff49dbbbea49e4d2bbe220085cc53600f]` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.
- `test_reviewed_candidate_detaches_only_target_and_keeps_ancestor_intact[189-2024-2023-modelo-189-fichero-2023-0-aeat-dr-189-2023-c493f8d9d927f28211336324cbe17ab7bae7b256d3c563273e01a76834757d6a]` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.
- `test_reviewed_candidate_detaches_only_target_and_keeps_ancestor_intact[189-2025-2023-modelo-189-fichero-2023-0-aeat-dr-189-2023-c493f8d9d927f28211336324cbe17ab7bae7b256d3c563273e01a76834757d6a]` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.
- `test_inherited_publication_keeps_thin_child_and_rolls_back_on_refusal[accepted]` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.
- `test_inherited_publication_keeps_thin_child_and_rolls_back_on_refusal[rollback]` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.

`dev/registry/pipeline/tests/test_m232_form_bridge.py`

- `test_detached_candidate_form_reproduces_generator_without_the_live_fragment_name` — FAILED; last report `20261007T134204.686138Z-pytest-32336-e2b05171`.

`dev/registry/pipeline/tests/test_m390_dana_reduction_design_semantic_map.py`

- `test_m390_dana_reduction_design_bijects_every_parser_anchor_to_the_reviewed_revision_owner` — FAILED; last report `20261007T134204.686138Z-pytest-32336-e2b05171`.

`dev/registry/pipeline/tests/test_m390_dana_reduction_retirement_semantic_map.py`

- `test_m390_dana_reduction_retirement_bijects_every_parser_anchor_to_the_reviewed_revision_owner` — FAILED; last report `20261007T134204.686138Z-pytest-32336-e2b05171`.

`dev/registry/pipeline/tests/test_m390_recargo_page_relayout_semantic_map.py`

- `test_m390_recargo_relayout_reuses_522_predecessor_anchors_and_pins_the_exact_page_2_delta` — FAILED; last report `20261007T134204.686138Z-pytest-32336-e2b05171`.

`dev/registry/pipeline/tests/test_render_profile.py`

- `test_profile_authority_has_no_legacy_tree_or_layout_oracle` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.

`dev/registry/pipeline/tests/test_target_currentness_grade.py`

- `test_the_same_tree_proven_at_filing_grade_is_refused` — FAILED; last report `20261007T134204.686138Z-pytest-32336-e2b05171`.

`dev/registry/tests/test_bundled_artifact_facts_agree_across_sources.py`

- `test_every_source_citing_one_bundled_file_declares_one_origin` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.
- `test_a_row_that_restates_one_origin_differently_is_detected` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.

`dev/registry/tests/test_casilla_bindings_name_their_own_sheet.py`

- `test_no_generated_field_binds_another_sheet_while_its_own_casilla_exists` — FAILED; last report `20261007T134204.686138Z-pytest-32336-e2b05171`.
- `test_no_generated_field_uses_an_unexplained_cross_sheet_binding` — FAILED; last report `20261007T134204.686138Z-pytest-32336-e2b05171`.

`dev/registry/tests/test_casilla_export_refs_derivation.py`

- `test_a_row_mapped_binding_field_derives_the_back_reference_of_the_casilla_its_slot_names` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.
- `test_a_binding_record_row_template_contributes_no_casilla_edge` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.

`dev/registry/tests/test_casilla_fragment_naming.py`

- `test_every_casilla_section_is_packed_and_owned_by_its_edition` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.

`dev/registry/tests/test_casilla_lineage_totality_gate.py`

- `test_every_unresolved_successor_row_is_refused_by_name_in_the_ledger` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.

`dev/registry/tests/test_continuidad_completeness_ratchet.py`

- `test_lineage_debt_matches_the_exact_named_ledger` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.

`dev/registry/tests/test_declaration_invariant_gates.py`

- `test_every_committed_export_tree_is_enrolled_in_its_reproduction_test` — PASSED; last report `20261007T145747.074734Z-pytest-62404-320f6cc2`.
- `test_every_public_module_in_the_registry_tooling_is_imported_by_a_test` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.

`dev/registry/tests/test_detail_record_modelo_coverage.py`

- `test_detail_record_modelo_emits_row_sets_with_localized_headers[349-2020-y-siguientes-collectible_invoice-2]` — FAILED; last report `20261007T134204.686138Z-pytest-32336-e2b05171`.

`dev/registry/tests/test_edition_delta_migration.py`

- `test_apply_publishes_a_modelo_whose_proof_is_clean` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.
- `test_work_directory_must_not_be_inside_the_registry_root` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.
- `test_work_directory_must_not_be_inside_the_production_source_tree` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.
- `test_work_directory_must_not_exist_before_migration` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.

`dev/registry/tests/test_export_field_value_round_trip.py`

- `test_patrimonio_checkbox_values_use_the_official_numeric_flags` — FAILED; last report `20261007T134204.686138Z-pytest-32336-e2b05171`.
- `test_every_fixed_width_record_preserves_populated_fields_at_its_declared_offsets[0]` — FAILED; last report `20261007T134204.686138Z-pytest-32336-e2b05171`.
- `test_every_fixed_width_record_preserves_populated_fields_at_its_declared_offsets[1]` — FAILED; last report `20261007T134204.686138Z-pytest-32336-e2b05171`.

`dev/registry/tests/test_facts_external_constants_retirement.py`

- `test_technical_configuration_boundary_matches_source` — FAILED; last report `20261007T134204.686138Z-pytest-32336-e2b05171`.

`dev/registry/tests/test_formula_modelo_registry_parity.py`

- `test_formula_revisions_are_owned_by_constructs_with_snapshot_workflow_surfaces` — FAILED; last report `20261007T134204.686138Z-pytest-32336-e2b05171`.

`dev/registry/tests/test_hand_authored_layouts_agree_with_type_column.py`

- `test_fields_the_schema_cannot_sign_are_exactly_the_declared_ones` — FAILED; last report `20261007T134204.686138Z-pytest-32336-e2b05171`.
- `test_a_planted_unsigned_field_is_reported_by_name` — FAILED; last report `20261007T134204.686138Z-pytest-32336-e2b05171`.
- `test_a_record_that_fits_no_sheet_is_unchecked_not_passed` — FAILED; last report `20261007T134204.686138Z-pytest-32336-e2b05171`.

`dev/registry/tests/test_loader_directory_mode.py`

- `test_committed_authored_sections_are_consolidated` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.

`dev/registry/tests/test_m303_did_account_wire_isolated_authority.py`

- `test_filing_envelope_facade_derives_ordered_bytes_from_the_canonical_resolver` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.
- `test_export_draft_routes_m303_only_through_the_full_envelope_and_refuses_open_authority` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.
- `test_filing_envelope_request_refuses_cross_source_or_digest_drift[envelope_update0-source` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.
- `test_filing_envelope_request_refuses_cross_source_or_digest_drift[envelope_update1-source` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.

`dev/registry/tests/test_m390_annual_manual_worked_example.py`

- `test_m390_annual_manual_worked_example_devengada_deducible_resultado` — PASSED; last report `20261007T151204.398781Z-pytest-84860-2b5c7508`.
- `test_m390_box_34_excludes_recargo_while_box_47_includes_it` — PASSED; last report `20261007T151204.398781Z-pytest-84860-2b5c7508`.
- `test_m390_annual_devengada_anti_tautology_recargo_changes_total` — PASSED; last report `20261007T151204.398781Z-pytest-84860-2b5c7508`.
- `test_m390_super_reducido_recargo_delta` — PASSED; last report `20261007T151204.398781Z-pytest-84860-2b5c7508`.

`dev/registry/tests/test_m390_auxiliary_envelope.py`

- `test_renders_each_real_modelo_390_header_once_before_parser_ordered_pages[aeat-dr-390-2022-2022-2022-2022]` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.
- `test_renders_each_real_modelo_390_header_once_before_parser_ordered_pages[aeat-dr-390-2023-2023-2023-2023]` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.
- `test_renders_each_real_modelo_390_header_once_before_parser_ordered_pages[aeat-dr-390-2024-2024-2024-2024]` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.
- `test_renders_each_real_modelo_390_header_once_before_parser_ordered_pages[aeat-dr-390-2025-2025-2025-y-siguientes-2025]` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.
- `test_refuses_reordered_numbered_pages` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.
- `test_refuses_mutated_header_geometry_and_literal` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.

`dev/registry/tests/test_modelo_131_2026_late_source_branch.py`

- `test_late_hydrated_delta_rekeys_only_four_source_changed_binding_slots` — FAILED; last report `20261007T134204.686138Z-pytest-32336-e2b05171`.

`dev/registry/tests/test_modelo_131_registry.py`

- `test_modelo_131_guidance_and_layout_sources_are_separated` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.

`dev/registry/tests/test_modelo_182_donor_surface_across_editions.py`

- `test_donor_surface_is_stated_once_on_the_earliest_edition` — FAILED; last report `20261007T134204.686138Z-pytest-32336-e2b05171`.
- `test_donor_bindings_and_construct_hydrate_in_every_authored_year` — FAILED; last report `20261007T134204.686138Z-pytest-32336-e2b05171`.

`dev/registry/tests/test_modelo_187_188_194_registry.py`

- `test_modelo_187_188_194_declare_no_formula[194]` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.
- `test_modelo_194_selects_only_its_three_hash_pinned_design_eras` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.
- `test_modelo_187_188_194_summary_is_the_printed_box_set[194-expected2]` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.

`dev/registry/tests/test_modelo_189_2022_edition.py`

- `test_each_edition_writes_the_moved_fields_where_its_design_prints_them[aeat-dr-189-2021-2022]` — FAILED; last report `20261007T134204.686138Z-pytest-32336-e2b05171`.
- `test_each_edition_writes_the_moved_fields_where_its_design_prints_them[aeat-dr-189-2023]` — FAILED; last report `20261007T134204.686138Z-pytest-32336-e2b05171`.
- `test_every_other_casilla_and_field_is_unchanged_across_the_designs` — FAILED; last report `20261007T134204.686138Z-pytest-32336-e2b05171`.

`dev/registry/tests/test_modelo_303_binding_source_repair.py`

- `test_free_2022_rate_does_not_enroll_an_unused_fixed_tier_binding` — FAILED; last report `20261007T134204.686138Z-pytest-32336-e2b05171`.
- `test_casilla_18_carries_the_binding_only_where_its_design_pins_the_tier[2022-False]` — FAILED; last report `20261007T134204.686138Z-pytest-32336-e2b05171`.

`dev/registry/tests/test_modelo_303_exonerado_390_endpoints.py`

- `test_real_official_binary_and_registry_agree_on_the_exact_exonerado_endpoint_set[2023-aeat-dr-303-2023-2023-2023-4T]` — FAILED; last report `20261007T134204.686138Z-pytest-32336-e2b05171`.
- `test_real_official_binary_and_registry_agree_on_the_exact_exonerado_endpoint_set[2024-hasta-08-y-2t-aeat-dr-303-2024-early-2024-2024-early-2T]` — FAILED; last report `20261007T134204.686138Z-pytest-32336-e2b05171`.
- `test_real_official_binary_and_registry_agree_on_the_exact_exonerado_endpoint_set[2024-desde-09-y-3t-aeat-dr-303-2024-late-2024-2024-late-4T]` — FAILED; last report `20261007T134204.686138Z-pytest-32336-e2b05171`.
- `test_real_official_binary_and_registry_agree_on_the_exact_exonerado_endpoint_set[2025-aeat-dr-303-2025-2025-2025-4T]` — FAILED; last report `20261007T134204.686138Z-pytest-32336-e2b05171`.
- `test_real_official_binary_and_registry_agree_on_the_exact_exonerado_endpoint_set[2026-y-siguientes-aeat-dr-303-2026-2026-2026-4T]` — FAILED; last report `20261007T134204.686138Z-pytest-32336-e2b05171`.
- `test_exonerado_endpoints_are_unique_canonical_manual_homes_without_parallel_producers` — FAILED; last report `20261007T134204.686138Z-pytest-32336-e2b05171`.

`dev/registry/tests/test_modelo_303_printed_total_check.py`

- `test_mutation_removing_the_predicate_lets_the_unprinted_total_through` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.
- `test_mutation_dropping_a_design_addend_breaks_design_parity` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.

`dev/registry/tests/test_modelo_390_base_imponible_bindings.py`

- `test_no_base_casilla_enters_an_annual_total_formula` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.

`dev/registry/tests/test_modelo_390_volumen_operaciones.py`

- `test_neither_volumen_box_feeds_any_total` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.

`dev/registry/tests/test_modelo_parity_coverage.py`

- `test_formula_bearing_modelos_have_constructs_and_model_specific_tests` — FAILED; last report `20261007T134204.686138Z-pytest-32336-e2b05171`.

`dev/registry/tests/test_monetary_scale.py`

- `test_the_unusual_decimal_count_is_reported_as_an_exception` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.
- `test_the_corpus_reports_no_sibling_scale_disagreement` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.

`dev/registry/tests/test_narrow_mechanism_admissions.py`

- `test_the_design_constant_admission_is_not_an_empty_filter` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.

`dev/registry/tests/test_record_design_modelo_131.py`

- `test_modelo_131_registry_bindings_cover_official_structured_records` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.

`dev/registry/tests/test_render_check.py`

- `test_every_record_drifting_tree_is_dispositioned_and_every_disposition_is_live` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.
- `test_every_manifest_stale_tree_really_does_reproduce_its_records` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.

`dev/registry/tests/test_revision_span_boundaries.py`

- `test_no_revision_spans_a_design_relayout` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.
- `test_the_verdict_names_a_mid_course_boundary_where_aeat_split_an_ejercicio` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.

`dev/registry/tests/test_schema_hygiene.py`

- `test_section_parts_are_snake_case` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.

`dev/registry/tests/test_support_matrix.py`

- `test_dormant_modelos_are_not_calc_grade` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.

`dev/tests/test_dev_tree_holds_no_run_output.py`

- `test_every_dev_internal_destination_is_a_declared_source` — FAILED; last report `20261007T134204.686138Z-pytest-32336-e2b05171`.

`dev/tests/test_fetch_boe_normative.py`

- `test_every_bundled_normative_is_already_canonical` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.

`dev/tests/test_first_party_source_is_defined_once.py`

- `test_no_development_module_restates_a_first_party_scope` — FAILED; last report `20261007T134204.686138Z-pytest-32336-e2b05171`.
- `test_vulture_excludes_exactly_what_the_authority_rejects` — FAILED; last report `20261007T134204.686138Z-pytest-32336-e2b05171`.
- `test_semgrepignore_excludes_exactly_what_the_authority_rejects` — FAILED; last report `20261007T134204.686138Z-pytest-32336-e2b05171`.
- `test_deptry_excludes_exactly_what_the_authority_rejects` — FAILED; last report `20261007T134204.686138Z-pytest-32336-e2b05171`.

`dev/tests/test_governance_corpus_isolation.py`

- `test_no_shipped_data_file_names_removable_scaffolding` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.

`dev/tests/test_no_broad_exception_raises.py`

- `test_no_broad_pytest_raises` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.

`dev/tests/test_no_home_directory_cache_paths.py`

- `test_no_unlisted_module_builds_a_path_from_the_home_directory` — FAILED; last report `20261007T134204.686138Z-pytest-32336-e2b05171`.

`dev/tests/test_precommit_policy.py`

- `test_setup_has_no_git_hook_installer_or_git_configuration_mutation` — FAILED; last report `20261007T134204.686138Z-pytest-32336-e2b05171`.

`dev/tests/test_repository_root_constants_resolve.py`

- `test_every_repository_root_constant_lands_on_the_repository` — FAILED; last report `20261007T134204.686138Z-pytest-32336-e2b05171`.

`dev/tests/test_wheel_bundles_corpus_and_registry.py`

- `test_wheel_archive_contains_every_runtime_data_file` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.

`dev/tests/test_wheel_content_boundary.py`

- `test_distributions_ship_only_the_product_package` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.

`src/cadrumo/_data/corpus/tests/test_corpus_provenance.py`

- `test_every_committed_provenance_document_enumerates_every_file_beside_it` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.

`src/cadrumo/adapters/inbound/declaracion/tests/test_verification_chain_m390.py`

- `test_verification_chain_m390_engine_recomputes_cuota_devengada_deducible[2022-0A-2022]` — FAILED; last report `20261007T134204.686138Z-pytest-32336-e2b05171`.
- `test_verification_chain_m390_engine_recomputes_cuota_devengada_deducible[2023-0A-2023]` — FAILED; last report `20261007T134204.686138Z-pytest-32336-e2b05171`.

`src/cadrumo/adapters/outbound/storage/tests/test_google_drive_sign_in_required.py`

- `test_the_probe_raises_sign_in_required_rather_than_reporting_drive_unreachable` — FAILED; last report `20261007T134204.686138Z-pytest-32336-e2b05171`.

`src/cadrumo/adapters/outbound/workbook/tests/test_review_workbook_xlsx.py`

- `test_ledger_materialization_has_no_fake_modelo_metadata` — FAILED; last report `20261007T134204.686138Z-pytest-32336-e2b05171`.

`src/cadrumo/adapters/persistence/profile/tests/test_binding_prefill.py`

- `test_modelo_390_prefill_compares_annual_totals_to_persisted_periodic_observations` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.

`src/cadrumo/adapters/persistence/profile/tests/test_modelo_390_303_reconciliation_continuity.py`

- `test_390_annual_reconciles_to_sum_of_303_quarters` — FAILED; last report `20261007T134204.686138Z-pytest-32336-e2b05171`.
- `test_modelo_390_reconciliation_enrolls_two_renta_years` — FAILED; last report `20261007T134204.686138Z-pytest-32336-e2b05171`.

`src/cadrumo/adapters/persistence/storage/custody/tests/test_custody_lock_order.py`

- `test_the_probe_fails_when_the_profile_lock_is_genuinely_held` — FAILED; last report `20261007T134204.686138Z-pytest-32336-e2b05171`.

`src/cadrumo/adapters/persistence/storage/custody/tests/test_kdf_supervision.py`

- `test_unavailable_canonical_root_has_no_weaker_supervision_fallback` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.

`src/cadrumo/adapters/persistence/storage/tests/test_namespace_registry.py`

- `test_secure_object_registry_preserves_the_declared_namespace_sequence` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.

`src/cadrumo/application/calculations/tests/test_revision_id_no_injection_regression.py`

- `test_no_new_snapshot_revision_id_injection_outside_named_exemptions` — FAILED; last report `20261007T134204.686138Z-pytest-32336-e2b05171`.

`src/cadrumo/application/filing/tests/test_modelo_303_exonerado_390_refusal.py`

- `test_exonerado_complete_revision_evidence_exports_page_four_without_override` — FAILED; last report `20261007T134204.686138Z-pytest-32336-e2b05171`.

`src/cadrumo/application/modelo/tests/test_invoice_withholding_capture_operation.py`

- `test_typed_annual_detail_preserves_all_canonical_fields_under_pinned_authority` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.

`src/cadrumo/application/modelo/tests/test_printed_boxes.py`

- `test_the_gates_printed_boxes_are_the_boxes_the_390_form_numbers` — FAILED; last report `20261007T134204.686138Z-pytest-32336-e2b05171`.
- `test_an_unresolved_390_imports_box_blocks_is_stored_and_named_by_its_printed_number` — FAILED; last report `20261007T134204.686138Z-pytest-32336-e2b05171`.
- `test_a_working_figure_the_390_form_does_not_number_is_neither_stored_nor_blocking` — FAILED; last report `20261007T134204.686138Z-pytest-32336-e2b05171`.

`src/cadrumo/application/modelo/tests/test_source_policy.py`

- `test_every_source_kind_has_exactly_one_policy` — PASSED; last report `20261007T150722.083603Z-pytest-41008-03c148e0`.
- `test_locked_and_carried_policies_are_exactly_the_calculation_ladder` — PASSED; last report `20261007T150722.083603Z-pytest-41008-03c148e0`.
- `test_a_kind_outside_the_ladder_is_never_claimed_locked_or_overridable` — PASSED; last report `20261007T150722.083603Z-pytest-41008-03c148e0`.
- `test_undecided_policies_are_the_kinds_nobody_has_classified` — PASSED; last report `20261007T150722.083603Z-pytest-41008-03c148e0`.
- `test_every_source_is_nameable_in_every_language[es]` — PASSED; last report `20261007T150722.083603Z-pytest-41008-03c148e0`.
- `test_every_source_is_nameable_in_every_language[en]` — PASSED; last report `20261007T150722.083603Z-pytest-41008-03c148e0`.
- `test_every_source_is_nameable_in_every_language[ca]` — PASSED; last report `20261007T150722.083603Z-pytest-41008-03c148e0`.
- `test_every_source_is_nameable_in_every_language[hu]` — PASSED; last report `20261007T150722.083603Z-pytest-41008-03c148e0`.

`src/cadrumo/application/modelo/tests/test_unresolved_binding_reported_once.py`

- `test_the_390_regularisation_left_unresolved_reads_as_one_note_on_its_box[resolver-names-the-box]` — FAILED; last report `20261007T134204.686138Z-pytest-32336-e2b05171`.
- `test_the_390_regularisation_left_unresolved_reads_as_one_note_on_its_box[resolver-bare]` — FAILED; last report `20261007T134204.686138Z-pytest-32336-e2b05171`.

`src/cadrumo/application/tests/test_preflight.py`

- `test_storage_root_error_when_ancestor_is_a_file` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.

`src/cadrumo/application/user_profile/tests/test_event_emission_contract.py`

- `test_required_setup_events_have_emission_sites` — FAILED; last report `20261007T134204.686138Z-pytest-32336-e2b05171`.

`src/cadrumo/core/errors/tests/test_exception_base_hygiene.py`

- `test_production_exception_classes_do_not_introduce_unregistered_builtin_roots` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.

`src/cadrumo/core/tests/test_currency_fields_use_one_annotation.py`

- `test_declared_exceptions_still_exist` — FAILED; last report `20261007T134204.686138Z-pytest-32336-e2b05171`.

`src/cadrumo/core/tests/test_settings_lifecycle_gate.py`

- `test_no_undeclared_module_chains_two_or_more_taxonomy_segments_into_a_literal_path` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.

`src/cadrumo/domain/calculations/registry/tests/test_clasificacion_casillas_oficiales.py`

- `test_m720_binding_derived_design_distinguishes_declared_binding_representation` — FAILED; last report `20261007T134204.686138Z-pytest-32336-e2b05171`.

`src/cadrumo/domain/calculations/registry/tests/test_modelo_390_rate_box_layer.py`

- `test_no_box_layer_casilla_enters_an_annual_total_formula` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.

`src/cadrumo/domain/calculations/registry/tests/test_modelo_390_rate_box_total_invariant.py`

- `test_no_rate_asserting_casilla_is_a_total_operand` — FAILED; last report `20261007T134204.686138Z-pytest-32336-e2b05171`.

`src/cadrumo/domain/calculations/registry/tests/test_modelo_390_recargo_rate_box_layer.py`

- `test_no_recargo_box_casilla_enters_an_annual_total_formula` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.
- `test_the_rate_blind_recargo_casillas_still_feed_the_devengada_total` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.

`src/cadrumo/entrypoints/cli/config/tests/test_misc_command_specs.py`

- `test_misc_config_target_schemas_resolve_and_own_canonical_identities` — FAILED; last report `20261007T134204.686138Z-pytest-32336-e2b05171`.

`src/cadrumo/entrypoints/cli/tests/test_profile_api_key_admission.py`

- `test_runtime_leaf_receives_explicit_api_method_before_local_session` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.

`src/cadrumo/entrypoints/cli/tests/test_profile_guard_action_recovery.py`

- `test_clean_root_refusal_executes_projected_profile_recovery_then_retries` — FAILED; last report `20261007T134204.686138Z-pytest-32336-e2b05171`.

`src/cadrumo/entrypoints/cli/tests/test_refusal_target_reconciliation.py`

- `test_target_reconciliation_equals_the_full_leaf_for_every_catalogue_target` — PASSED; last report `20261007T144655.852880Z-pytest-88904-9dc38d62`.

`src/cadrumo/entrypoints/tests/profile_persistence/test_dormant_m369_oss_resolver_live.py`

- `test_m369_exterior_period_calculate_review_export_e2e[EXT-1T-operation_date0-issued_at0-1T-01]` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.
- `test_m369_exterior_period_calculate_review_export_e2e[EXT-2T-operation_date1-issued_at1-2T-02]` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.
- `test_m369_exterior_period_calculate_review_export_e2e[EXT-3T-operation_date2-issued_at2-3T-03]` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.
- `test_m369_exterior_period_calculate_review_export_e2e[EXT-4T-operation_date3-issued_at3-4T-04]` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.
- `test_m369_live_path_folds_oss_invoices_not_no_live_source_advisory` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.
- `test_m369_zero_valued_oss_invoice_remains_verifiable` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.

`src/cadrumo/entrypoints/tests/profile_persistence/test_file_flow_events.py`

- `test_file_refuses_persisted_registry_revision_divergence` — FAILED; last report `20261007T134204.686138Z-pytest-32336-e2b05171`.
- `test_verify_emits_refused_event_on_missing_casilla` — PASSED; last report `20261007T145129.922409Z-pytest-83660-f4a17da2`.

`src/cadrumo/entrypoints/tests/profile_persistence/test_file_flow_verify.py`

- `test_verify_refuses_persisted_registry_revision_divergence` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.
- `test_verify_refuses_when_required_casilla_missing_real_registry` — PASSED; last report `20261007T145129.922409Z-pytest-83660-f4a17da2`.
- `test_verify_takes_modelo_347_counterparty_fields_from_their_rows_real_registry` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.

`src/cadrumo/entrypoints/tests/profile_persistence/test_m193_disclosure_phase_calculation.py`

- `test_a_settled_prior_accrual_row_refuses_the_collection_year_export` — PASSED; last report `20261007T145129.922409Z-pytest-83660-f4a17da2`.

`src/cadrumo/entrypoints/tests/profile_persistence/test_m210_irnr_income_ledger.py`

- `test_m210_gross_income_source_mode_keeps_manual_and_ledger_authority_exclusive` — PASSED; last report `20261007T145129.922409Z-pytest-83660-f4a17da2`.
- `test_m210_ledger_mode_evidence_bundle_records_no_manual_gross_income` — PASSED; last report `20261007T145129.922409Z-pytest-83660-f4a17da2`.

`src/cadrumo/entrypoints/tests/profile_persistence/test_modelo_210_inmobiliaria_e2e.py`

- `test_m210_inmobiliaria_advisory_fires_through_real_calculate_and_verify` — PASSED; last report `20261007T145129.922409Z-pytest-83660-f4a17da2`.
- `test_m210_inmobiliaria_advisory_silent_when_base_computes_nonzero` — PASSED; last report `20261007T145129.922409Z-pytest-83660-f4a17da2`.

`src/cadrumo/entrypoints/tests/profile_persistence/test_modelo_347_declarado_rows.py`

- `test_bucket_calculation_persists_and_replays_one_declarado_record_per_counterparty_and_clave` — FAILED; last report `20261007T134204.686138Z-pytest-32336-e2b05171`.
- `test_operator_supplied_rows_reach_the_same_draft_records` — FAILED; last report `20261007T134204.686138Z-pytest-32336-e2b05171`.

`src/cadrumo/entrypoints/tests/profile_persistence/test_renta_annual_reconciliations_fold_in_live.py`

- `test_m190_verify_accepts_observation_backed_m111_cross_period_evidence` — PASSED; last report `20261007T145129.922409Z-pytest-83660-f4a17da2`.
- `test_m190_verify_accepts_filed_1t_m111_and_attested_no_obligation_zero_quarters` — PASSED; last report `20261007T145129.922409Z-pytest-83660-f4a17da2`.
- `test_m190_verify_refuses_a_work_income_row_missing_its_family_data` — PASSED; last report `20261007T145129.922409Z-pytest-83660-f4a17da2`.

`src/cadrumo/entrypoints/tests/profile_persistence/test_row_field_template_input_refusal.py`

- `test_a_scalar_input_outside_every_row_field_template_still_calculates` — PASSED; last report `20261007T145129.922409Z-pytest-83660-f4a17da2`.

`src/cadrumo/entrypoints/tests/profile_persistence/test_verify_report_idempotent_collapse.py`

- `test_identical_nongranting_verify_retry_collapses_to_one_report` — PASSED; last report `20261007T145129.922409Z-pytest-83660-f4a17da2`.
- `test_distinct_outcome_verify_produces_a_distinct_report` — PASSED; last report `20261007T145129.922409Z-pytest-83660-f4a17da2`.

`src/cadrumo/entrypoints/tests/test_operation_catalogue.py`

- `test_every_claimed_projection_joins_a_real_surface` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.

`src/cadrumo/entrypoints/tui/modelo/workbench/tests/test_grid_tables_real.py`

- `test_390_page_2_draws_each_group_as_its_own_base_and_tax_table` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.
- `test_the_cursor_moves_cell_by_cell_and_keeps_its_column` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.
- `test_a_box_the_form_sets_shows_its_figure_or_a_dot_and_never_a_word` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.

`src/cadrumo/entrypoints/tui/modelo/workbench/tests/test_held_values_and_sources.py`

- `test_no_rate_cell_on_a_real_layout_shows_a_figure_without_a_percent_sign[390-0A-2025]` — FAILED; last report `20261007T124327.041872Z-pytest-39812-287949c0`.

`src/cadrumo/entrypoints/tui/modelo/workbench/tests/test_workbench_finding_words.py`

- `test_the_walk_reaches_the_live_producers` — PASSED; last report `20261007T163049.180959Z-pytest-10044-9f47f02d`.
- `test_every_fact_a_producer_supplies_has_one_declared_way_of_being_written` — PASSED; last report `20261007T163049.180959Z-pytest-10044-9f47f02d`.
- `test_every_finding_reads_in_words_in_every_language[es]` — PASSED; last report `20261007T163049.180959Z-pytest-10044-9f47f02d`.
- `test_every_finding_reads_in_words_in_every_language[en]` — PASSED; last report `20261007T163049.180959Z-pytest-10044-9f47f02d`.
- `test_every_finding_reads_in_words_in_every_language[ca]` — PASSED; last report `20261007T163049.180959Z-pytest-10044-9f47f02d`.
- `test_every_finding_reads_in_words_in_every_language[hu]` — PASSED; last report `20261007T163049.180959Z-pytest-10044-9f47f02d`.
- `test_a_missing_value_of_the_operator_records_is_named_by_its_heading_and_leads_to_the_table` — PASSED; last report `20261007T163049.180959Z-pytest-10044-9f47f02d`.

`src/cadrumo/entrypoints/tui/tests/test_installed_session.py`

- `test_each_requester_receives_the_same_fully_validated_public_contract_set[login]` — PASSED; last report `20261007T130432.363194Z-pytest-42272-df87b63d`.
- `test_each_requester_receives_the_same_fully_validated_public_contract_set[api]` — PASSED; last report `20261007T130432.363194Z-pytest-42272-df87b63d`.
- `test_each_requester_receives_the_same_fully_validated_public_contract_set[api_reference]` — PASSED; last report `20261007T130432.363194Z-pytest-42272-df87b63d`.
- `test_each_requester_receives_the_same_fully_validated_public_contract_set[human]` — PASSED; last report `20261007T130432.363194Z-pytest-42272-df87b63d`.
- `test_requester_contracts_are_shared_across_recomposition_but_fresh_in_a_separate_session` — PASSED; last report `20261007T130432.363194Z-pytest-42272-df87b63d`.

`src/cadrumo/tests/test_dev_dotenv_bridge.py`

- `test_operator_dotenv_keys_are_bridged_into_the_environment` — FAILED; last report `20261007T134204.686138Z-pytest-32336-e2b05171`.

`src/cadrumo/tests/test_docstring_core_struct_links.py`

- `test_modules_that_use_a_core_struct_link_it` — FAILED; last report `20261007T134204.686138Z-pytest-32336-e2b05171`.
- `test_public_functions_link_anchor_parameters` — FAILED; last report `20261007T134204.686138Z-pytest-32336-e2b05171`.

`src/cadrumo/tests/test_spanish_iva_stem_conformance.py`

- `test_non_python_package_paths_use_the_canonical_iva_stem` — FAILED; last report `20261007T134204.686138Z-pytest-32336-e2b05171`.
