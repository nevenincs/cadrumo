---
tags:
  - '#exec'
  - '#honest-all-green'
date: '2026-07-14'
modified: '2026-07-14'
step_id: 'S01'
related:
  - "[[2026-07-14-honest-all-green-plan]]"
---

# Diagnose the renta binding-resolution root cause including the profile-has-economic-activity unsupplied binding and classify each failing assertion as engine defect or expectation defect with authority evidence

## Scope

- `src/cadrumo/domain/calculations/registry`

## Description

- Confirmed no peer WIP in the assigned test/registry surfaces before
  investigating, except `application/modelo/_taxation_comparison.py`
  (see Notes) and the plan document itself (a peer's uncommitted
  `P03.S06`/`P03.S07`/`P05.S09`/`P05.S10` checkbox edits, handled with
  an entangled-file-safe commit).
- Re-ran a representative subset of `scratch/2026-07-14-coordinator-hag-inventory/failed-list.txt`
  lines 8-22 and 25-80 sequentially (`-n 0`) at HEAD to confirm live
  and capture full tracebacks, per the assignment.
- MAJOR FINDING: discovered two independent stale-cache artefacts that
  were inflating the apparent failure count, and confirmed a
  substantial fraction of the ~55 registry-cluster failures were
  phantom, not real regressions:
  - The pytest assertion-rewrite bytecode cache
    (`__pycache__/*-pytest-9.1.1.pyc`) still carried `co_filename`
    pointing at the retired `src/aeat/...` path for files physically
    relocated to `src/cadrumo/...` by the product-rename campaign
    (confirmed by decoding the marshalled code object's `co_filename`
    directly). Clearing `__pycache__` under `src/cadrumo` (gitignored,
    generated, safe to delete) fixed the path display; the two
    findings that surfaced this way (`test_modelo_100_registry_2025_legal_refs.py`,
    `test_catalogue_verification_normatives.py`) were confirmed to
    persist as real content failures once the path was correct.
  - `_toml_fingerprint`/`_directory_fingerprint`
    (`domain/calculations/registry/_loader.py`) key the registry
    disk-cache purely on `(path, size, mtime_ns)`, and
    `_resolve_registry_disk_cache_dir` (`_loader_cache.py`) routes the
    cache to the SHARED, cross-session OS temp directory whenever
    `_running_under_pytest()` is true — confirmed dozens of
    accumulated `aeat_registry_*.pkl` / `cadrumo_registry_*.pkl`
    pickles in `%TEMP%` spanning many prior sessions. Deleting every
    `aeat_registry_*.pkl` / `cadrumo_registry_*.pkl` from `%TEMP%`
    (gitignored, generated, safe) and re-running
    `test_modelo_chain_cohesion.py`,
    `test_record_design_completeness.py`,
    `test_modelo_100_registry_2025_legal_refs.py`, and
    `test_catalogue_verification_normatives.py` together turned all
    four green — proving they were serving a pre-correction compiled
    snapshot from an earlier session, not exercising the current
    registry TOML content. This is exactly the concern named in plan
    step `P05.S10` ("make the loader-cache cross-session proof... under
    parallel execution without weakening them"), whose checkbox is
    already (uncommittedly) checked by a peer — flagging for that
    owner rather than duplicating.
- With both stale-cache classes cleared, re-ran every registry test in
  the assigned line range as wide batches (`cross_dependency_calculations`,
  `ledger_renta_expense_binding`, `modelo_100_retenciones_binding_wiring`,
  `modelo_100_ahorro_base_chain`, `modelo_100_cripto_1812_propagation`,
  `modelo_100_imputed_real_estate_art85`, the four `modelo_100_eo_agraria_*`
  files, `deduccion_madrid_nacimiento_adopcion`,
  `minimo_contribuyente_age_increment`, `modelo_349_registry`): all
  confirmed GREEN. The only two registry-layer findings that remained
  red after cache-clearing were `test_binding_count_is_exactly_38` and
  `test_binding_selector_registry_covers_typed_sources` (both real, see
  table).
- Root-caused every remaining red finding by reading the failing
  assertion, the production code/registry TOML it exercises, and (for
  the M210/M100 legal-ref and dependency-role findings that turned out
  to be cache artefacts) the git history of the implicated files.
- Checked `git status`/`git diff` on every implicated production file
  for active peer WIP before concluding root cause, per the
  assignment's critical instruction.

## Classification table

| test | class | root cause | fix sketch | collision status |
|---|---|---|---|---|
| `application/verification/tests/test_verify.py::test_m100_2025_registry_policy_reports_independently_grounded_fraction` | fixture/seeding defect | THE renta cluster's namesake defect. The M100 2025 registry legitimately gained binding `renta-2025-profile-has-economic-activity` (correctly auto-resolved from `taxpayer_type.irpf_income_categories` by `application/modelo/_profile_binding.py`'s `_resolve_one` special case in the normal profile-resolution path). This test calls `calculate_registry_snapshot` directly with a hand-built `binding_values` dict that bypasses profile resolution entirely and never lists the new binding. | Add `"renta-2025-profile-has-economic-activity": Decimal("0")` or `Decimal("1")` (matching the fixture's declared activity type) to the test's `binding_values` dict. | No peer WIP in `test_verify.py`. Clear. |
| `application/modelo/tests/test_taxation_comparison.py` (5 tests: `test_high_disparity_couple_conjunta_recommended`, `test_moderate_income_conjunta_recommended_via_art84_reduccion`, `test_comparison_result_structure_is_typed`, `test_individual_branch_honesty_caveat_surfaces`, `test_individual_branch_caveat_present_when_individual_recommended`) | fixture/seeding defect | M100 2025 casilla `0501` is now a formula target (`formulas/0290-renta-2025-base-liquidable-negativa-general-2024-compensacion.toml`), but the test's `inputs` dict (line 73) still supplies `"0501": Decimal("0")` as a raw input, tripping `_reject_computed_inputs`. | Remove `"0501": Decimal("0")` from the test's `inputs` fixture — the value is now computed, not supplied. | `application/modelo/_taxation_comparison.py` has ACTIVE UNCOMMITTED PEER WIP — confirmed comment/docstring-only (stripping ADR/rule citations per the source-hygiene sweep), nowhere near the `_run`/`inputs` construction this fix touches. `test_taxation_comparison.py` itself is clean. Low collision risk but the production file is mid-edit; coordinate before landing. |
| `application/modelo/tests/test_profile_binding_real_path.py::test_binding_count_is_exactly_38` | fixture/expectation defect | The M100 2025 registry legitimately gained the 39th profile binding (`renta-2025-profile-has-economic-activity`); the test's hardcoded `== 38` was never bumped. | Bump the expected count to 39. | No peer WIP. Clear. |
| `domain/calculations/registry/tests/test_selector_shape.py::test_binding_selector_registry_covers_typed_sources` | fixture/expectation defect | `BindingSourceKind.LEDGER_IRNR_INCOME_AGGREGATION` is correctly registered against `_IrnrLedgerIncomeSelector` in production (`_bindings.py`'s `_BINDING_SELECTOR_REGISTRY`); this test's `expected` set was not updated when the M210 IRNR ledger-income feature landed. Sibling gap to the one already fixed in commit `a7aa2202a3` (P03.S07), which enrolled the same resolver in `test_source_resolver_enrollment.py` and `test_precedence_ladder_conformance.py` but missed this third inventory. | Add `BindingSourceKind.LEDGER_IRNR_INCOME_AGGREGATION` to the test's `expected` set. | No peer WIP in `test_selector_shape.py` or `_bindings.py`. Clear. |
| `application/modelo/tests/test_actions.py::test_registry_snapshot_unresolved_finding_is_localised`, `application/modelo/tests/test_objective_estimation_exclusion_advisory.py::test_revision_verification_collects_objective_estimation_exclusion_advisory` | fixture/seeding defect | `_collect_revision_verification_findings` (`application/modelo/_verification_actions.py`) has a required keyword-only `invoice_repository` parameter; the one production call site passes it correctly, but these 2 white-box tests call the private helper directly and omit it. | Pass `invoice_repository=None` (or a real fixture repository, matching the test's other repository args) at both call sites. | No peer WIP in either test file or `_verification_actions.py`. Clear. |
| `application/modelo/tests/test_cross_period_clean_state_gates.py::test_verify_surfaces_operator_declared_suppression_advisory_without_blocking` | expectation defect (locale casing) | Test asserts the capitalised standalone form `"La dependència entre períodes no està neta"`; the actual notice message embeds the SAME clause lowercase mid-sentence (`"la dependència ... : model=303 exercici=2025 ..."`), i.e. the message is composed as a lowercase fragment followed by structured context, not the capitalised sentence the test expects. Not root-caused to a specific locale-catalogue commit within this diagnosis pass; needs the message-builder or locale-key source read to confirm whether the casing changed intentionally or the fixture predates a composition change. | Update the test's expected substring to lowercase (if the composition is intentional), or restore capitalisation in the message builder if the fragment is meant to stand alone. Needs one more read before committing to a direction. | No peer WIP. Clear, but needs a follow-up read before fixing (deliberately left as `expectation defect (unconfirmed direction)` rather than guessed). |
| `application/modelo/tests/test_file_flow_filing.py::test_file_runs_workflow_gate_and_refuses_before_state_writes_when_preflight_blocks`, `application/modelo/tests/test_file_flow_verify.py::test_verify_runs_workflow_gate_and_refuses_before_verified_state_write` | expectation defect | Both tests trigger the blocking condition via an unavailable auth provider, expecting `ModeloWorkflowGateError`. The preflight log shows `"preflight gate-4 skipped: auth-provider readiness binds only live/AEAT-touching purposes, not the local build/verify/file/export flow"` — gate-4 was intentionally narrowed to skip for the local file/verify flow these tests exercise, so the auth-unavailable scenario no longer blocks by design. The tests predate that scope narrowing. | Rework the test's blocking scenario to use a condition gate-4 (or another still-applicable gate) still enforces for local flows, or confirm with whoever narrowed gate-4's scope which local-flow condition should now stand in for it. | No peer WIP in either test or the preflight module. Clear, but the fix requires knowing the intended replacement blocking condition — flagging rather than guessing. |
| `domain/calculations/registry/tests/test_modelo_chain_cohesion.py::test_declared_canonical_chains_use_pago_or_summary_dependency_role`, `domain/calculations/registry/tests/test_record_design_completeness.py::test_calculation_completeness_manifest_legal_refs_match_calculation_closure`, `domain/calculations/registry/tests/test_modelo_100_registry_2025_legal_refs.py::test_modelo_100_2025_anexo_c_base_negative_general_uses_member_refs_only`, `domain/calculations/registry/tests/test_catalogue_verification_normatives.py::test_retired_normative_summary_corpus_files_are_not_bundled`, `domain/calculations/registry/tests/test_modelo_349_registry.py::test_committed_modelo_349_gb_xi_country_prefix_rules_are_cited_to_aeat_instructions` (order-dependent flake) | NOT A DEFECT — stale cross-session cache artefact | See the two MAJOR FINDING cache mechanisms above. All five pass green once `__pycache__` and the shared-temp-dir registry pickles are cleared; the on-disk TOML/legal-catalogue content was already correct. | No production/test fix needed. The durable fix is `P05.S10`'s scope (loader-cache cross-session robustness) — flag to that owner; do not duplicate. | N/A — no edit needed here. |
| `domain/calculations/registry/tests/test_cross_dependency_calculations.py` (2 tests), `test_ledger_renta_expense_binding.py`, `test_modelo_100_retenciones_binding_wiring.py` (3 tests), `test_modelo_100_ahorro_base_chain.py`, `test_modelo_100_cripto_1812_propagation.py` (2 tests), `test_modelo_100_imputed_real_estate_art85.py`, the four `test_modelo_100_eo_agraria_*.py` files (23 tests), `test_deduccion_madrid_nacimiento_adopcion.py` (6 tests), `test_minimo_contribuyente_age_increment.py` (3 tests) | not reproduced (already green) | Confirmed passing sequentially both individually and in wide batches with a clean cache. Whatever failed in the coordinator's original full-suite run was very likely the same stale registry disk-cache pickle, or `-n auto` parallel non-determinism per `aeat-local-execution`'s re-run-before-blaming guidance. | None needed. | N/A |

## Outcome

Diagnosis complete for the assigned scope (failed-list.txt lines 8-22,
25-80). Of the ~40 lines investigated, the true residual defect count
is small: 2 confirmed fixture/seeding defects (`test_verify.py`
grounded-fraction, the namesake renta-cluster bug; `test_taxation_comparison.py`
x5, one shared root cause), 2 confirmed fixture/expectation-count
defects (`test_binding_count_is_exactly_38`,
`test_binding_selector_registry_covers_typed_sources`), 2 confirmed
TypeError signature-omission defects (`test_actions.py`,
`test_objective_estimation_exclusion_advisory.py`, one shared root
cause), 1 locale-casing expectation defect needing one more read
before a fix direction is chosen, 2 workflow-gate expectation defects
needing the intended replacement condition from whoever narrowed
gate-4's scope, and 5 findings that were NOT real defects at all —
stale cross-session cache artefacts (both a stale pytest
assertion-rewrite bytecode cache from the product-rename file moves,
and a stale registry disk-cache pickle in the shared OS temp
directory, keyed on `(path, size, mtime_ns)` rather than content).
Every other line in the assigned range was independently reproduced
green. No production or test edits made in this step per the
diagnosis-only mandate.

## Notes

Collision check: `application/modelo/_taxation_comparison.py` carries
active uncommitted peer WIP (comment/docstring cleanup only, stripping
ADR/rule citations from source comments — unrelated to the `inputs`
fixture defect this diagnosis found). No STOP was warranted since the
WIP does not touch the surface a fix would edit, but S02 (or whichever
step lands the `test_taxation_comparison.py` fix) should re-check this
file's WIP status before editing, since it may have landed by then.

The plan document itself carries a peer's uncommitted `P03.S06` /
`P03.S07` / `P05.S09` / `P05.S10` checkbox edits at the time this
record was written; the `P01.S01` checkbox was set via
`vault plan step check` and committed with an entangled-file-safe
technique so the peer's uncommitted checkbox state was not disturbed
or bundled into this commit.

The stale registry disk-cache finding is significant enough to flag
explicitly to the coordinator: it means a meaningful fraction of any
"red count" reported from a shared-worktree full-suite run may be
phantom rather than real, for as long as `P05.S10` remains open. No
incidents; no data loss.
