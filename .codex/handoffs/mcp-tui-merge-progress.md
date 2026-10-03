## Deletions to stage (git rm)
- src/cadrumo/entrypoints/tui/ledger_doors.py (LANE2; UD)
- src/cadrumo/entrypoints/auth_configuration.py (WP-C)
- src/cadrumo/application/auth/configuration_submission.py (WP-C)
- src/cadrumo/application/auth/configuration_result.py (WP-C)
- src/cadrumo/core/errors/tests/test_public_error_projection.py (WP-C)
- src/cadrumo/entrypoints/cli/tests/test_auth_configure_profile_door.py (WP-C)
- src/cadrumo/entrypoints/tui/tests/test_installed_generation_composition.py (WP-C; UD)
- src/cadrumo/entrypoints/tui/profile/tests/test_local_reader_page.py (WP-C; UD)
- dev/acceptance/retenciones/installed_tui_withholding.py (WP-C; UD)
- src/cadrumo/entrypoints/tui/tests/test_modelo_projection_reader.py (WP-C; moved to entrypoints/tests/)
## New files to stage
- src/cadrumo/entrypoints/runtime/tests/test_operation_host_authority_release.py (LANE2)
- src/cadrumo/entrypoints/tui/profile/runtime_auth_configuration.py (WP-C)
- dev/init/contract.py, dev/init/probe.py, dev/env/_install.py, dev/env/_venv.py, dev/env/tests/test_install.py, dev/env/tests/test_venv_lock.py (ADMIN restore)
## Follow-ups to report to operator
- MCP removed the TUI withholding destination (runtime_unavailable); our workbench-driven retenciones TUI acceptance is gone.
- MCP removed the TUI local-reader page; profile overview document-reader card has nothing wired to it.
- Pre-existing: dev/registry/form_layout has no just recipe or wiring-census entry.
- Failing, inherited: core error-hygiene/registry tests (MCP and ledger classes); test_runtime_censal_preview projection_profile_id1-updated.
## Exclude from merge commit (tui-bb separate work)
- dev/audit/complexity.py, dev/audit/tests/test_complexity_scan.py, dev/audit/tests/test_complexity_scope_scan.py
- Also pre-existing dirty paths at session start that are not merge resolution: check `git diff --cached` vs worktree before commit.
## Kept from tui-bb
- tui/launcher.py main(): release_bundled_indexed_authority after orderly session + 2 tests in test_launcher_entry_point.py
## Pre-existing on our tip (2833fb4de3), not merge-caused (per WP-A)
- test_calculation_route RELATED_PARTY_OPERATION (2 tests), test_row_producing_binding_uses_its_detail_row_channel (M232) — reference retired items.
## WP-A out-of-list edit
- src/cadrumo/entrypoints/tests/modelo_operator_work_storage.py (executor context double: cancellation, operands)
## LANE1 done (19 files): locales x12, dev/locales x3, connect-an-agent md + 3 po
- Pre-existing on our tip (not merge): test_machine_secret_diagnostics x3 (formal es expectation); product-identity 11 bare "Cadrumo" keys; casilla diacritics (3 values); docs localization failures on reference/identity-and-naming.md, workstation-setup.md.
- Final locale pass pending: deletion guard rerun, prune ~102 unread keys, register dynamic prefixes, resume_refused_ scanner artifact.
- Other lanes' items surfaced: runtime_modelo_verification_report_read.py:33 non-literal message_locale_key (x3 tests); dict-constant naming in runtime_invoice_catalogue.py, runtime_ledger_inventory.py, tui/profile/overview.py; language-override inventory drift.
## LANE2 done: native-session CLI 45/45; unit/contract green on its files
- D (Codex split): src/cadrumo_harness/mcp/protocol_contract.py:15 imports ProjectionPage from core.async_cleanup; defined in application/runtime/projection_pages.py. Recheck at gate time.
- E: application/aggregation/tests/test_modelo_source_mesh_ledger.py 7 failures, RegistryValidationError 2022 M303 invoice IVA screen shape missing (ledger_iva_bindings:713). Classify: pre-existing on tip vs merge.
- C: CLI M123 count-authority refusal now renders registered code (TUI expectation) not REFUSED_CLI_BOUNDARY (MCP expectation) - note for review.
- Codex split: check AuthorityStoreError import source in src/cadrumo_harness/mcp/* (DEDUP report)
## WP-A done
- PUBLIC INTERFACE CHANGE: modelo.work.calculate refuses inputs/detail rows unless caller_context="explicit"; default replays head (keeps operator work). Tell operator / MCP integrators.
- Pre-existing on tip: test_calculation_route x2 (RELATED_PARTY_OPERATION), test_row_producing_binding_uses_its_detail_row_channel (M232).
- 23 CLI tests REFUSED_LOCAL_RUNTIME -> LANE2 porting to native harness.
- Gate check: application/operations/registry_schema_validation.py got a `# type: ignore` from the Codex lane (no-suppression rule) - verify at gate.
- WP-A also edited: test_verify_ledger_drift_gate.py (_transaction helper), entrypoints/tests/modelo_operator_work_storage.py, the 3 caller tests.
## WP-B done (round 1)
- Deletions: tui/modelo/view/overview.py, tui/modelo/view/tests/test_modelo_projection_reader.py; test_declarations_installed_create.py -> being PORTED (round 2), not deleted.
- ADMIN fix: verification report restore moved to projection.to_report()/to_finding() (application/modelo/verification_report_read_operation.py); CLI runtime_modelo_verification_report_read.py delegates. 24 tests pass.
- Open: conformance census ~58 MCP ops without scenario (check if pre-existing on MCP tip); native login timeout 25s (WP-B round 2); hu picker 80 cols (LANE1).
- Pre-existing-ish ty: test_runtime_account_factories.py:147 redundant cast.
- INHERITED FROM MCP TIP: conformance census test_every_registered_definition_has_a_conformance_scenario fails — ~58 MCP-registered ops (config.google.*, ledger.export, modelo.m145.*, modelo.quickfile, diagnostics.*, auth.apoderado.*, review_package.*, ...) have no scenario on MCP's tip either.
- tui-bb fixed (not merge file, leave unstaged): dev/registry/edition_delta_migration.py:717,751 Codex split slip.
## Type-check triage (ty whole tree, 122 diagnostics)
- Inherited, identical to MCP tip (platform/self-attr): macos_keychain_store.py (74), test_macos_keychain_native (2), macos_manager (1), windows_inheritance_fixture (2), test_windows_job_inheritance_native (2), agent_eval ctypes.get_last_error (1), agent_eval set() L276 (1), test_borrador_100 (2; test+callee identical to MCP tip), test_runtime_account_factories redundant cast (1, identical to MCP).
- Pre-existing on our tip: test_calculation_route (2).
- Pending deletion/port: tui/modelo/view/overview.py (5), test_declarations_installed_create.py (3).
- Codex/non-merge: dev/registry edition_* (21), dev/quality/import_checker.py (2; edited 17:59, merge doesn't change it -> leave unstaged).
- FIXED by ADMIN: activity_asset_operation_test_support.py legal_reference (2).
## Staging policy
- Stage all merge-touched paths in working-tree state (includes Codex splits of merge files) + new split modules they import; leave non-merge edits unstaged. Verify by exporting index to scratch (git checkout-index --prefix) and import-smoking it before commit.
## LANE2 calculate CLI port: 18/27 pass; 9 fail on MCP runtime regressions (kept honest)
- F1 (8 tests): entrypoints/cli/runtime_registered_operation.py:250-274 submitted_operation_error drops worker error context/message params; refusals lose typed reason, row identity, remedy; internal faults lose classification; REFUSED_MODELO_PROFILE_READINESS renders raw %{...} placeholders. Needs bounded refusal-detail projection (MCP runtime contract).
- F2 (2 tests): entrypoints/cli/runtime_modelo_calculation.py:38 fixed 120 s wait; M100/M200 calc completes after it, and a successful write is reported as REFUSED_CLI_BOUNDARY runtime_deadline_exceeded.
- Runtime flake: runtime_connection_closed under xdist (3 native cases), serial passes.
## WP-B round 2
- test_declarations_installed_create.py PORTED (native harness, windows_only, 1 passed 253 s). Not deleted.
- FOLLOW-UP for operator (MCP lane, costly decision): worker admission margin. Cold compose 10-14 s (97% strict_model_json_schema over 550 bindings, no reuse) inside fixed _WORKER_ADMISSION_PREPARE_TIMEOUT_SECONDS=30 (profile_worker.py:85) and rotation reconnect min(20, remaining) (profile_password_rotation.py:218); client budget 75 s (profile_access.py:43). Options: (a) build-time schema contract artifact + --check gate, (b) process-wide schema memo + compose at worker start, (c) lazy per-definition. Plus derive worker deadline from client remaining.
- Test-side parity in progress: in-process hosts prepare_registry() before login; native tests use production default budget.
## WP-B round 3 (test parity)
- prepare_registry() before login at 3 native hosts (test_runtime_workbench_native.py:417,:765; test_declarations_installed_create.py:229); 5 login calls moved to production default 75 s.
- Native serial run under 100% CPU load: 2 passed, 2 failed post-login (session expired at status check after generation read :591; launcher autopilot 90 s root-load wait :788). RERUN AT GATE on quieter machine; if still failing, phase-time read_workbench_generation.
- Not changed: test_runtime_password_rotation.py 25 s (may assert rotation budget); ~70 inline RuntimeProfileConnections hosts.

# HANDOFF (usage limit reached) — merge feature/mcp (5c0eeca84b) into feature/tui, pre-merge HEAD 2833fb4de3
State: `git merge --no-commit` in progress in Y:/code/cadrumo-worktrees/tui; ALL 95 paths still unmerged in the index (nothing staged); no conflict markers left in src/dev/packaging/docs.
Done: LANE1 (locales, awaiting final pass), LANE2 (all #708 ports + CLI test ports), WP-A, WP-B, WP-C, ADMIN mechanical/provisioning(b)/doors/composition/verification-report restore/activity-asset support.
IN FLIGHT / NEXT:
1. WP-D (F1 refusal detail projection + F2 120 s wait) STOPPED MID-EDIT at turn limit in entrypoints/cli/runtime_registered_operation.py, runtime_modelo_calculation.py and runtime refusal projection modules (it was writing a settlement helper gated on the definition's refusal-detail opt-in). Resume it or re-dispatch; acceptance = LANE2's 9 failing assertions in the 5 calculate CLI test files pass unweakened.
2. LANE1 final locale pass (deletion guard rerun, prune ~102 unread keys, dynamic prefixes, scanner f-string fix) + any keys WP-D needs.
3. tui-bb will send edits for application/aggregation/modelo_bindings.py and application/modelo/projection.py; tui-bb's other edits stay unstaged; tui-bb republishes authority AFTER merge commit.
4. Codex lane split fix: src/cadrumo_harness/mcp/protocol_contract.py:15 ProjectionPage import -> cadrumo.application.runtime.projection_pages. Check `# type: ignore` in application/operations/registry_schema_validation.py.
5. Gates: regenerate import_load_targets.json, application_entrypoint_modules.json (owners), docs/_sequences (just docs-generate-sequences), env reference, docs api; prune stale import_boundary_ratchet entries; vaultspec-core vault check all --fix; just check-code/types/import-boundaries/locales; test-tui/cli/unit; rerun 2 native workbench tests on quiet machine.
6. Staging: git add all merge paths; git rm deletions listed above; leave non-merge edits unstaged (dev/audit, import_checker, dev/registry edition_*, tui-bb binding work); export index (git checkout-index -a --prefix=<scratch>/) and import-smoke; then ASK OPERATOR before commit.
Operator follow-ups: worker admission cold-compose margin (a/b/c); TUI withholding + local-reader removed by MCP; form_layout census gap; caller_context interface change.

# RESUMED 21:5x
- Index was fully staged at 21:46 by an unknown writer (not tui-bb; likely Codex lane). Content marker-free. Will rebuild staging from stage/include.txt (2594) / stage/exclude.txt (266) via stage/classify.py (rerun after WP-D + regeneration).
- LANE1 final pass done (scanner JoinedStr, catalogues 20:05). protocol_contract ProjectionPage fixed.
- tui-bb: all writes stopped in tui; held binding edits not needed pre-commit; post-commit it fixes dev/registry/pipeline/_tree_publication.py:580 NameError (non-merge) and republishes authority.
- WP-D resumed.

# 23:5x STATUS — commit blocked on operator decision
- WP-D DONE (F1 refusal detail via encrypted OperationErrorDetailV1 + operation.error_detail v1; F2 settlement up to 1 h, LOCKED_CLI_OPERATION_STILL_RUNNING exit 7). Locale key already existed. New files: core/errors/record_fault.py, application/operations/error_detail.py + 3 tests.
- ledger_doors.py removed from disk.
- Snapshot tooling ready: stage/snapshot.sh (temp index, export, isolated import check).
- FINDING: Codex lanes (complexity 981 paths, duplication 290, registry-health 42 per their .vault ledgers) are interleaved with merge files byte-for-byte; precise merge-only separation not feasible. Snapshot with Codex src but excluded dev/registry fails 60 imports (facts/schema.py split -> payloads.py/variants.py).
- Live Codex breakage: retenciones_bindings.py ResolvedMappingFact under TYPE_CHECKING used in isinstance (NameError at M111 executor).
- Churn still active (~25 py files / 5 min at 23:20). Quiet watcher running (b49x8yew4).
- DECISION NEEDED: (A) commit whole tree minus tui-bb binding/scope/audit work after Codex pause + fix its breakage + verify; (B) hold merge until Codex done; (C) whole tree incl. tui-bb.
- WP-D residual follow-ups: profile_mutations.py fixed wait (F2-class) on `config profile edit`; stale M111 "all-blank" test wording; auth test_auth_operation_definitions 2 failures (pre-existing per WP-D).
