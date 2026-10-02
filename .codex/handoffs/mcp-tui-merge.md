# Handover prompt: land `feature/tui` (via `main`) into `feature/mcp`

Prepared 2026-10-02 from a collision-anticipation session, then independently reviewed; the verified corrections are folded in. Nothing was merged or committed on any shared branch. All numbers below come from trial merges of snapshots taken at 2026-10-02T12:50Z. Re-run the reproduction commands at the end before relying on them; both source worktrees had active sessions with uncommitted work. At review time `feature/tui` had moved to `494357b819`, and the committed-only conflict count was unchanged at 94.

MCP's in-flight edits change the collision itself (the browser-channel setting and the runtime shutdown path), so re-snapshot after that session commits.

## Your job and boundary

Merge the TUI work into `feature/mcp` once the TUI PR has landed on `main`, and leave a tree that passes the owning gates. The repository rules apply in full: no stash, reset, restore, clean, rebase, amend or force operations; preserve other sessions' uncommitted edits; commit, push or merge only on the operator's request. One item below still needs an operator decision before you resolve it (marked **DECISION**).

## Operator decisions (2026-10-02)

- **Auth is MCP.** MCP's runtime path is the canonical auth-provider configuration (cluster 2). Carry the TUI's auth behavior into it, then retire the TUI's parallel path.
- **Locales: union them.** Resolve the catalogue conflicts as a key-level union of both branches: keep both sides' additions and honor deletions (cluster 5).
- **Regenerate `docs/_sequences`.** Never hand-merge them (cluster 6).
- **Semantic breakage needs careful orchestration.** The functionality of both branches must be respected. Resolve the breaks case by case from an architectural-intent overview, not by letting one side win by default (cluster 1).

## Topology at snapshot time

| Ref | Commit | Notes |
| --- | --- | --- |
| `feature/mcp` | `5c0eeca84b` | 45 commits past its last `main` merge, at `cb6cd50ad8` (#703). Worktree `Y:/code/cadrumo-worktrees/mcp` had 109 uncommitted paths (S10 of `2026-09-26-mcp-purpose-authentication-plan` in flight). |
| `feature/tui` | `181cea4c52` | 270 commits past `origin/main`; already contains `origin/main` `a92f1aef2e` (#708). Worktree `Y:/code/cadrumo-worktrees/tui` had 102 uncommitted paths. |
| `origin/main` | `a92f1aef2e` | 3 squash commits past MCP's base: #714 (headless browser provisioning in `dev.init`), #715 (Python minor pin), #708 (registry continuity). |
| local `main` | `e4af6d64c6` | 1 local-only commit not on origin; adds one more conflict (`.importlinter`) if it lands. |

`main` lands PRs as squash commits. After the TUI PR lands, merging `main` into `feature/mcp` uses base `cb6cd50ad8`. A direct `feature/mcp` ← `feature/tui` merge (base `fa6599ae1c`) produced the identical conflict set, so either route sees the same surface.

## Scratch worktree (disposable)

`Y:/code/cadrumo-worktrees/mcp-tui-collision`: detached; HEAD `ca6bf959a5` (commit of MCP's live worktree state); `MERGE_HEAD` `847b5205d9` (simulated squash of TUI's live state onto `origin/main`). An uncommitted trial merge is in progress there, with 110 unmerged paths and the conflict markers in place. Use it to read hunks (`git diff --name-only --diff-filter=U`, `git diff <path>`, `git show :2:<path>` / `:3:<path>`). Do not commit there, and do not develop the real merge there: its HEAD contains another session's uncommitted work frozen at snapshot time. When finished, ask the operator to remove it (`git worktree remove --force` is theirs to run).

## Collision surface at a glance

| Measure | Committed branches only | Including both worktrees' uncommitted edits |
| --- | --- | --- |
| Textual conflicts | 94 (82 content, 12 modify/delete) | 110 (98 content, 12 modify/delete) |
| Of which reproduced by merging `origin/main` alone | — | 56 |
| Paths changed on both sides | — | 204. 96 auto-merge cleanly (91 truly modified on both sides, 3 deleted on both, 2 carried across renames); review those too |
| Imports that resolve on each side but break after the merge | — | 97 references in 28 files (5 of those files also conflict) |
| Field, keyword-argument and method breaks (invisible to the import scan) | — | about 24 (reviewer's field scan; a lower bound) |
| Locale keys changed differently on both sides | — | 0 |
| Deleted locale keys still read by surviving code | — | at least 5 (`operation.modal.terminal.*`) |

Raw outputs (merge-tree logs, import scan JSON, scripts, and the reviewer's field scan under `review/`) are in this session's scratchpad, `C:/Users/hello/AppData/Local/Temp/claude/Y--code-cadrumo-worktrees-mcp/143df483-2d3c-4ff8-97b2-83c13339a9f7/scratchpad/`. It may be cleaned up, so regenerate from the commands at the end if it is gone.

## Clusters, in resolution order

### 1. Architecture: TUI frontends vs MCP's local runtime (largest risk)

Accepted `2026-09-26-mcp-purpose-authentication-adr` (shared local runtime; "Authenticated local workbench projections") and `2026-09-26-mcp-purpose-authentication-profile-access-adr` ("Mandatory CLI/TUI feature parity") route CLI and TUI through the local runtime's registered operations. They replace the in-process topology of `2026-09-04-tui-architecture-authenticated-tui-visibility-adr`. MCP implemented this by gutting `entrypoints/tui/launcher.py` (−1607 lines) and `installed_session.py` (−452), deleting `tui/operations/controller.py`, `tui/ledger_doors.py`, `tui/profile/local_reader.py` and `tui/secret/login.py`, and adding `tui/runtime_workbench.py`, `tui/operations/runtime_controller.py`, `adapters/local_runtime/`, `entrypoints/runtime/` and `application/*/operation_definitions.py` enrollments.

The TUI branch built the Modelo editor workbench, declarations pages and profile-setup UX on the old in-process wiring (`2026-09-30-modelo-editor-workbench-adr`, `-operator-layer-adr`, `2026-10-02-...-companion-cutover-adr`; none of them mentions the runtime). It also deleted `tui/modelo/view/*`, `tui/modelo/routes.py` and `tui/modelo/installed_workspace.py`, replacing them with `tui/modelo/workbench/`.

**How to resolve: orchestrated, case by case (operator decision).** Both branches' functionality must survive. Don't lose any TUI capability (workbench editing, declarations, profile setup, auth flows, visual and accessibility fixes), and don't weaken any MCP runtime guarantee (profile admission, grant custody, process ownership, CLI/TUI/MCP parity). Neither side wins by default, and neither textual hunk choice is the answer.

1. **Architectural-intent overview first.** Before editing, read both branches' governing records whole: the two MCP purpose-authentication ADRs, the amended TUI architecture ADRs, and the three `modelo-editor-workbench` ADRs. Write down what each branch set out to achieve and where those intents meet: which TUI capabilities need a runtime operation, a projection, or a frontend-only change. If that overview shows an accepted decision must change, take an ADR amendment to the operator before writing code against it.
2. **One case per break.** For each item below and each conflicted TUI/application file, record:
   - the TUI capability it carries and the MCP mechanism it collides with;
   - where the merged behavior lives (the owning operation, projection or screen);
   - the test that proves both sides' behavior still holds.

   Don't restore a deleted module just to make an import resolve, and don't delete TUI behavior because its old wiring is gone.
3. **Orchestrate the writers.** Give one writer to each tightly coupled surface:
   - operation definitions and composition roots;
   - the TUI launcher, session and runtime workbench;
   - the TUI workbench, declarations and profile pages.

   Sequence them so definitions settle before the frontends that consume them. Review the integrated result against the overview, not file by file.

Breaks the merge introduces (each is a case). Take the first one first.

- **The Modelo lifecycle door contract diverged. This is the first and largest case.** `ModeloWorkspaceLifecycleDoor` differs between the branches:
  - **MCP:** requires `submit_operation`, has no `services`, keeps `edit_baseline`, and has `apply_edits(scalar_values, binding_values)`.
  - **TUI:** keeps `services`, adds `edit_admission`/`edit_renewal`/`edit_preflight`/`edit_refusals`, `admit_edit_baseline()` and `preflight_edits()`, and has `apply_edits(baseline, scalar_intents, binding_intents)`.

  Effects:
  - About 21 construction sites in 11 cleanly merged TUI files pass `services=` without `submit_operation`: `modelo/tests/test_lifecycle_edit_door.py`, eight `workbench/tests/*` and `tui/tests/modelo_workbench_session.py`.
  - `workbench/installed.py` calls `door.preflight_edits` and `door.edit_refusals`, which MCP's door lacks.
  - MCP's `modelo/runtime_lifecycle.py` passes the `edit_baseline=` field that the TUI removed.

  The TUI's edit admission, preflight and renewal surfaces need runtime operations: `application/modelo/edit_preflight.py`, `edit_refusal_projection.py`, and `renew_modelo_edit_baseline` in `edit_admission.py`. Settle the `modelo.edit.apply` request contract and those operations before touching any workbench screen.
- `tui/modelo/workbench/{installed,ports,screen}.py` and `workbench/tests/workbench_fixture.py` import `tui.operations.controller.OperationController`, which MCP deleted. Type them against MCP's port, `tui.operations.controller_port.OperationControllerPort`, which is what MCP's own doors use (for example, `modelo/lifecycle.py`). The concrete `RuntimeOperationController` is built only in the `runtime_*` adapters.
- They also import `application.modelo.operation_definitions.ModeloExportPublicResultV2`. MCP's `application.modelo.export_projection.ModeloExportPublicResultV3` is not a rename. It adds `fichero_boe` and `calculation_report` receipts with a validator, and sets `result_version=3`. `workbench_fixture.py` and `test_export_result_screen.py` must supply the receipts. MCP also moved the calculate, discard, verify and file result schemas to v2.
- MCP's `tui/runtime_workbench.py` imports `tui.modelo.installed_workspace.compose_installed_modelo_workspace_factory`, which the TUI deleted. Rewire it to the TUI workbench composition.
- `tui/modelo/view/overview.py` and `view/tests/test_modelo_projection_reader.py` (modify/delete): the TUI deleted the package and MCP edited these files. Port MCP's intent into `workbench/`, then delete them. MCP's `tui/tests/test_runtime_workbench_native.py:112` imports `modelo.view.overview.ModeloWorkspaceOverviewScreen`, which resolves only while the deleted file lingers, so that test must move to the workbench screen in the same change.
- The TUI removed `application.workbench_generation.ModeloWorkspaceProjectedReadV1` and the `WorkbenchGenerationInputsV1.modelo_graded_refusals` field. MCP's `entrypoints/workbench_generation_composition.py` and `application/tests/test_workbench_generation_operation.py` still use them.
- These import launcher symbols that MCP removed (`compose_installed_workbench_root`, `operation_services_scope`, `InstalledWorkbench{Account,Root,FactoryDependencies,RootComposition}*V1`, `TuiOperationCompositionV1`, `compose_installed_workbench_generation_provider`, `run_authenticated_workbench_sessions`, `_modelo_projection_reader`): `dev/tui/harness/{profile_fixtures,sequences}.py`, `tui/declarations/tests/test_declarations_installed_create.py`, `tui/tests/test_auth_frontend_uniformity.py`, `tui/tests/test_launcher_entry_point.py` (conflicted), `tui/tests/test_modelo_projection_reader.py`, `tui/tests/test_installed_generation_composition.py` (MCP deleted it).
- `tui.secret.login.LoginScreen` and `tui.secret.passphrase.build_profile_passphrase_change_door` (both removed by MCP) are used by `tui/installed_session.py` (conflicted) and `dev/acceptance/retenciones/installed_tui_withholding.py` (MCP deleted it; the TUI modified it).
- The TUI moved files out of `tui/modelo/view/` (for example, `view/tests/test_m303_evidence_lifecycle.py` became `modelo/tests/`). MCP hunks applied across such renames keep relative imports at the old depth (`....operations.controller_port`, `...lifecycle`), so re-level them. Check every rename-carried MCP edit for this.
- New TUI-side application surfaces (`application/modelo/work_form_{service,sources,result}.py`, `domain/modelos/calculation_revision_operator_layer.py`, `entrypoints/calendar_evidence_composition.py`): find which a frontend reaches in-process, and enroll those as registered operations for runtime and CLI parity. Not yet traced in detail. Expect conflicts in `application/modelo/operation_definitions.py` (8 hunks), `workspace_models.py`, `calculation_actions.py`, `verification_actions.py`, `work_review.py`, `workbench_generation.py`, and in the TUI `declarations/*`, `modelo/lifecycle.py` and `profile/overview.py`.

### 2. Duplicate auth-provider configuration (decided: MCP)

Both branches built a shared CLI/TUI auth-provider configuration independently:

- MCP (`d97b241d68`): `application/auth/provider_configure_operation_access.py` and `cli/config/runtime_auth_configure.py`, routed through the profile runtime.
- TUI (`f1503bc78f`, `90661f7f71`, plus uncommitted tests): `entrypoints/auth_configuration.py`, `application/auth/configuration_submission.py` and `configuration_result.py`, submitted in-process through `operation_composition`.

They collide in `application/auth/operation_definitions.py`, `application/auth/operator.py`, `cli/config/_auth.py`, `entrypoints/operation_composition.py` and `tui/installed_session.py`. The architecture rules forbid parallel implementations.

The operator decided that auth is MCP: the runtime path is canonical. Carry every TUI auth behavior into it, including profile-bound saves, preserved public failure metadata, the shared CLI/TUI supervised configuration and the TUI auth-frontend uniformity flows. Port the TUI's auth tests (including its uncommitted `test_auth_configure_profile_door.py` and `test_auth_profile_configuration.py`) onto the MCP path, so they keep proving that behavior. Then delete the TUI's parallel path and its import-target and API-doc entries.

Two contract details:

- **Public result contract (reviewer-reported; verify before acting).** Both sides bind `auth.configure` result schema v1 to different models:
  - MCP's projection carries `result.file`, a path.
  - The TUI's `AuthConfigurePublicResultV1` deliberately carries no private path (`certificate_file_provided`, `changed`) and emits `OperationEffect.NONE` on a no-op.
  - The TUI also adds `clave_movil_route` and `expected_profile_revision`/`expected_profile_digest` to the request.

  Carry the redaction, the no-op effect and the profile baseline into the MCP contract, and bump its schema version rather than reusing v1 for a different shape.
- **Duplicate error concept, merged cleanly.** `core/errors/hierarchy.py` ends up with both MCP's `RecordedRegisteredError` and the TUI's `PublicErrorProjectionError`, and both are special-cased in `error_codes.get_registered_error_code`. The TUI's only consumer is the auth path being retired, so unify on one.

### 3. Dev provisioning: `dev.init` retired vs extended (**DECISION**)

MCP `cd81de5986` retired `dev.init` and `dev/env/{_install,_venv}.py` and folded provisioning into `just setup` (`uv sync` + `python -m dev.env setup`). `main` #714/#715 extended `dev.init` instead: `just setup` runs `uv run --isolated --no-project --python 3.13 -- python -m dev.init all`, adds `setup-check`, `setup-repository-tools`, `dev/env/playwright_setup.py` and `dev/env/environment_state.py`, and changes Dockerfile, devcontainer and `env/.env.example`. No ADR covers either side. The operator must choose:

- (a) keep MCP's retirement and port #714/#715 behavior (browser-channel provisioning, Linux deps, `CI`-stripped installs, Python minor pin) into `dev.env` and `just setup`; or
- (b) adopt `main`'s `dev.init` and drop MCP's retirement.

Affected:
- 6 `dev/init/*` modify/delete conflicts;
- `justfile` (4 hunks: `init`, `setup`, `setup-check`, `setup-browser`, test markers);
- `dev/env/{__main__,playwright_doctor}.py` and its test;
- `env/.env.example`, `src/cadrumo/core/config.py` and `dev/tests/test_dev_cli_justfile_wiring.py`.

The three `packaging/*/hatch_build.py` conflicts are docstring wording only, not provisioning.

Details either option must handle:
- **Browser channel (part of this decision).** The `config.py` conflict is MCP's uncommitted deletion of `Settings.cadrumo_browser_channel`. #714's cleanly merged `dev/env/playwright_setup.py` reads it, and `Dockerfile`, `.devcontainer/devcontainer.json` and `env/.env.example` set `CADRUMO_BROWSER_CHANNEL`. `playwright_setup.py` also calls `run_doctor(channel=)`, which MCP's `playwright_doctor` lacks. This breaks under both options unless the channel setting's fate is decided too.
- **Under (b):** MCP also deleted `dev/init/contract.py` and `probe.py` without a conflict, yet `main`'s `dev/init/*` and the new `dev/init/tests/test_process.py` import them. MCP also removed:
  - the `dev.exit_codes.INIT_*` names;
  - the `pyproject.toml` per-file ignores for `dev/init/*`;
  - `init` from the `exhaustive = True` dev-lanes contract in `.importlinter`.

  Restore all of these together.
- **Under (a):** drop `main`'s `dev/init/tests/`, and remove the deleted `dev.env._install` dependency from the cleanly merged `dev/env/environment_state.py`.

### 4. Port `main` #708 into MCP's rewrites

- **`src/cadrumo_harness/mcp/server.py`.** MCP rewrote it (+895/−1328) and deleted `_corpus_tools.py` and `_completions.py`; don't restore those modules. #708 added `release_bundled_indexed_authority()` after an orderly transport shutdown.
  - #708's cleanly merged test, `mcp/tests/test_server_shutdown_release.py`, calls the private `server._serve_until_orderly_shutdown`. That design disarms a stdio watchdog MCP removed.
  - MCP's runtime host holds a lifetime authority lease (`entrypoints/runtime/operation_host.py:198`, `lease_operation()`). The release only takes effect after that lease's exit stack closes.
  - Port it to the runtime shutdown path (`entrypoints/runtime/shutdown.py`, which has uncommitted MCP edits), and rewrite the test against that path.
- **#708 removed a field that new MCP code still uses.** #708 removed `PerModeloAggregationCommand.withholding_observations` (`application/aggregation/service.py`), but MCP's new `application/modelo/aggregate_public.py` (around lines 283 and 307) still reads and constructs it. Port to #708's withholding source resolution (the reviewer names `load_calculation_withholding_rows` and `WithholdingSourceResolver`). This also breaks any pre-merge of `origin/main`.
- `entrypoints/cli/_modelo_aggregate_cli.py` (9 hunks, about 540 lines): MCP rewrote it for operation enrollment; #708 changed the aggregation surface. Re-apply #708's semantics on MCP's structure. The same pattern applies to `_actividad_asset_cli.py`, `_ledger_evidence{,_review}_cli.py`, `ledger_evidence_extraction_composition.py`, `tui/ledger/{evidence,models}.py` and the withholding aggregate CLI tests.
- `dev/packaging/tests/test_installed_oracles.py` still imports `dev.packaging.installed_mcp_oracle`, which MCP deleted (`9d38fe7b00`).
- Registry data: the TUI side touches about 890 registry files (including #708); MCP touches none. There is no textual collision, but the merged tree needs a fresh authority publication. Publish it before any CLI/TUI gate or sequence run. Check that MCP's pinned publication provenance (`5c0eeca84b`) still matches #708's authority identity; this was not verified.

### 5. Locale catalogues (decided: union)

The 12 catalogue conflicts (`common.yml`, `errors.yml`, `cli.yml` × en/es/ca/hu) are adjacent edits. Across all 20 catalogue files changed on both sides, a key-level three-way comparison found zero keys changed differently on both sides.
- MCP: per locale, about 287 additions, 2–3 value changes and 16 deletions.
- TUI: 874 (en), 1,086 (es), 1,176 (ca) and 3,280 (hu) value changes, plus about 6,700 additions and 1,927 deletions. The operator decided to union them through the canonical locale workflow (`just locales-*`), not by hand-picking hunks.

Union means a key-level three-way merge, not "every key ever seen". Take both branches' additions and value changes, and honor deletions. Since the base, the TUI side deleted 1,927 English keys (with matching es/ca/hu removals) and MCP deleted 16 (for example `mcp.call.timeout` and the `mcp.elicitation.confirm.*` family). A naive union would bring all of them back and fail the unused-key coverage gate.

Before honoring a deletion, check that no surviving code still reads the key. Use the live source scanner and also grep each deleted key literally; the scanner alone is not enough. For example:
- the TUI deleted `operation.modal.terminal.{succeeded,refused,cancelled,timed_out,interrupted}`;
- `tui/operations/projection.py` (unchanged on both sides) still reads them through a `Literal` alias, as does `dev/acceptance/income_tax/tui_journey.py`;
- about 47 literal hits on deleted keys survive in the merged `.py` files.

Where a deleted key is still read, keep it and record it as a cluster 1 case. Re-run the key-level comparison after the final merge; if any key differs on both sides, stop and raise it. Then apply the TUI's new `aeat-locales-cli` bullet (informal singular address in es/ca/hu) to every MCP-authored value. A rough marker scan already found formal forms, for example `tui.runtime_login.reference_invalid` ("Introduzca…", "Introduïu…") and about 13 Hungarian values. Also covers `dev/locales/{_spelling,fstring_registry}.py` and `dev/locales/tests/test_audit.py`.

### 6. Generated surfaces: regenerate, never hand-merge

- `docs/_sequences/**` (17 conflicts plus 26 auto-merged paths). The operator decided to regenerate them: take either side for the conflicted files, then regenerate them all with `just docs-generate-sequences` once code, locales and authority have settled, and verify with `just docs-sequences-check`. MCP has uncommitted changes to `dev/docs/sequences/{runner,compare}.py`, so wait for them to be committed.
- `docs/how-to/connect-an-agent.md`: MCP's rewrite vs the TUI's informal-register wording. Resolve the source, run `just docs-generate-catalogs`, then re-translate the changed msgids in the three `.po` files in the informal register.
- `dev/quality/metadata/import_load_targets.json`: run `just generate-import-load-targets`.
- `application_entrypoint_modules.json` still lists the deleted `tui.modelo.view.*`. Regenerate it through its owner; the reviewer names `python -m cadrumo.tests.module_target_inventory`.
- `dev/quality/metadata/import_boundary_ratchet.json` is **not** generated. It holds 191 hand-owned entries (owner, reason, `expires_on`). Its stale `cli.app_live_justificante_composition` and `cli.ledger_llm_composition` entries already exist on MCP's tip, so prune them by hand.
- `docs/reference/environment-overrides.md` is generated from `Settings` by `python -m dev.docs.env_reference`. Regenerate it after `config.py` and the browser-channel decision settle.
- `uv.lock` and `pyproject.toml` auto-merged. MCP added `jeepney`, `secretstorage`, the `cadrumo-runtime` script and the `_data/local_runtime/**` package data; #715 changed the Python pin (`.python-version`, release cohort). Re-lock rather than trusting the textual merge.
- `docs/api/*.rst`: both sides moved and deleted modules. Verify with `just check-docs-api` after the code settles.

### 7. Vault

There is one conflict, in the frontmatter of `.vault/plan/2026-08-11-tui-architecture-plan.md` (`related:` links). Keep both the MCP ADR link and the TUI audit link, then run `vaultspec-core vault check all --fix` to recompute `modified` and `body_hash`. ADRs and plans are otherwise additive. MCP amended the TUI architecture ADRs, so read `2026-08-11-tui-architecture-adr` and `2026-09-04-tui-architecture-authenticated-tui-visibility-adr` as amended; they feed the cluster 1 architectural-intent overview. If resolving a case changes any accepted MCP or TUI decision, record that through an ADR amendment; do not just write code against it.

## Full conflict list (live snapshot, 110)

`(m/d)` = modify/delete. `[tui]` = caused by TUI-own work; unmarked conflicts already reproduce when merging `origin/main` alone.

- **Vault** (1): `.vault/plan/2026-08-11-tui-architecture-plan.md`
- **Dev provisioning, packaging, env** (18): `dev/env/__main__.py`, `dev/env/playwright_doctor.py`, `dev/env/tests/test_playwright_doctor.py`, `dev/init/README.md` (m/d), `dev/init/__init__.py` (m/d), `dev/init/__main__.py` (m/d), `dev/init/plan.py` (m/d), `dev/init/process.py` (m/d), `dev/init/stamp.py` (m/d), `dev/packaging/tests/test_installed_oracles.py`, `dev/tests/test_dev_cli_justfile_wiring.py`, `docs/reference/environment-overrides.md`, `env/.env.example`, `justfile`, `packaging/authority/hatch_build.py`, `packaging/cadrumo_data_manuals/hatch_build.py`, `packaging/cadrumo_data_official/hatch_build.py`, `src/cadrumo/core/config.py`
- **Locale catalogues and locale tooling** (15): `dev/locales/_spelling.py`, `dev/locales/fstring_registry.py` [tui], `dev/locales/tests/test_audit.py` [tui], `src/cadrumo/locales/ca/cli.yml` [tui], `src/cadrumo/locales/ca/common.yml`, `src/cadrumo/locales/ca/errors.yml`, `src/cadrumo/locales/en/cli.yml` [tui], `src/cadrumo/locales/en/common.yml`, `src/cadrumo/locales/en/errors.yml`, `src/cadrumo/locales/es/cli.yml` [tui], `src/cadrumo/locales/es/common.yml`, `src/cadrumo/locales/es/errors.yml`, `src/cadrumo/locales/hu/cli.yml` [tui], `src/cadrumo/locales/hu/common.yml`, `src/cadrumo/locales/hu/errors.yml`
- **Generated docs sequences** (17): `docs/_sequences/explanation/how-renta-is-assembled/renta-assembly-provenance.json`, `docs/_sequences/how-to/file-at-aeat/file-at-aeat-chain.json`, `docs/_sequences/how-to/filing-readiness/filing-readiness-dependencies.json`, `docs/_sequences/how-to/modelo-100/modelo-100-dependencies.json`, `docs/_sequences/how-to/modelo-100/modelo-100-export-file.json`, `docs/_sequences/how-to/modelo-100/modelo-100-inspect-inputs.json`, `docs/_sequences/how-to/modelo-303/modelo-303-first-quarter.json`, `docs/_sequences/how-to/modelo-303/modelo-303-inspect-boxes.json`, `docs/_sequences/how-to/modelo-303/modelo-303-revision.json`, `docs/_sequences/how-to/modelo-349/modelo-349-inspect.json` [tui], `docs/_sequences/how-to/modelo-390/modelo-390-annual-2025.json` [tui], `docs/_sequences/how-to/modelo-390/modelo-390-inspect.json`, `docs/_sequences/how-to/profile-setup/profile-setup-delete.json`, `docs/_sequences/how-to/review-calculation-values/review-values-bindings.json` [tui], `docs/_sequences/how-to/troubleshooting/troubleshooting-ledger-ready.json` [tui], `docs/_sequences/how-to/troubleshooting/troubleshooting-period-grammar.json`, `docs/_sequences/how-to/troubleshooting/troubleshooting-toolbox.json` [tui]
- **User docs and PO translations** (4): `docs/how-to/connect-an-agent.md` [tui], `docs/locales/ca/LC_MESSAGES/how-to/connect-an-agent.po` [tui], `docs/locales/es/LC_MESSAGES/how-to/connect-an-agent.po` [tui], `docs/locales/hu/LC_MESSAGES/how-to/connect-an-agent.po` [tui]
- **Quality metadata (generated)** (2): `dev/quality/metadata/application_entrypoint_modules.json` [tui], `dev/quality/metadata/import_load_targets.json`
- **TUI entrypoints** (19): `src/cadrumo/entrypoints/tui/declarations/controller.py` [tui], `src/cadrumo/entrypoints/tui/declarations/models.py` [tui], `src/cadrumo/entrypoints/tui/declarations/overview.py` [tui], `src/cadrumo/entrypoints/tui/declarations/routes.py` [tui], `src/cadrumo/entrypoints/tui/installed_session.py` [tui], `src/cadrumo/entrypoints/tui/launcher.py`, `src/cadrumo/entrypoints/tui/ledger/evidence.py`, `src/cadrumo/entrypoints/tui/ledger/models.py`, `src/cadrumo/entrypoints/tui/ledger/tests/test_invoice_entry_lines.py` [tui], `src/cadrumo/entrypoints/tui/ledger_doors.py` (m/d), `src/cadrumo/entrypoints/tui/modelo/lifecycle.py` [tui], `src/cadrumo/entrypoints/tui/modelo/tests/test_export_result_screen.py` [tui], `src/cadrumo/entrypoints/tui/modelo/tests/test_m303_evidence_lifecycle.py` [tui], `src/cadrumo/entrypoints/tui/modelo/view/overview.py` (m/d) [tui], `src/cadrumo/entrypoints/tui/modelo/view/tests/test_modelo_projection_reader.py` (m/d) [tui], `src/cadrumo/entrypoints/tui/profile/overview.py` [tui], `src/cadrumo/entrypoints/tui/profile/tests/test_local_reader_page.py` (m/d) [tui], `src/cadrumo/entrypoints/tui/tests/test_installed_generation_composition.py` (m/d) [tui], `src/cadrumo/entrypoints/tui/tests/test_launcher_entry_point.py`
- **CLI entrypoints** (14): `src/cadrumo/entrypoints/cli/_actividad_asset_cli.py`, `src/cadrumo/entrypoints/cli/_ledger_evidence_cli.py`, `src/cadrumo/entrypoints/cli/_ledger_evidence_review_cli.py`, `src/cadrumo/entrypoints/cli/_modelo_aggregate_cli.py`, `src/cadrumo/entrypoints/cli/_modelo_readiness_cli.py` [tui], `src/cadrumo/entrypoints/cli/_modelo_rendering.py` [tui], `src/cadrumo/entrypoints/cli/_modelo_work_calculate_cli.py` [tui], `src/cadrumo/entrypoints/cli/_modelo_work_wizard_cli.py` [tui], `src/cadrumo/entrypoints/cli/config/_auth.py` [tui], `src/cadrumo/entrypoints/cli/tests/test_ledger_evidence_batch_cli.py`, `src/cadrumo/entrypoints/cli/tests/test_ledger_payment_capital_withholding_aggregate_cli.py`, `src/cadrumo/entrypoints/cli/tests/test_ledger_payment_withholding_aggregate_cli.py`, `src/cadrumo/entrypoints/cli/tests/test_modelo_190_withholding_detail_gate.py` [tui], `src/cadrumo/entrypoints/cli/tests/test_modelo_requires_data_inventory.py`
- **Composition roots** (4): `src/cadrumo/entrypoints/adapter_composition.py` [tui], `src/cadrumo/entrypoints/ledger_evidence_extraction_composition.py`, `src/cadrumo/entrypoints/operation_composition.py` [tui], `src/cadrumo/entrypoints/tests/profile_persistence/test_verify_ledger_drift_gate.py` [tui]
- **Application, core, adapters, harness, acceptance** (16): `dev/acceptance/retenciones/installed_tui_withholding.py` (m/d) [tui], `src/cadrumo/adapters/persistence/storage/sql/_secure_object_writes.py` [tui], `src/cadrumo/adapters/persistence/storage/tests/test_m303_calculate_evidence_admission.py` [tui], `src/cadrumo/application/aggregation/modelo_bindings.py` [tui], `src/cadrumo/application/aggregation/modelo_bindings_renta_expenses.py` [tui], `src/cadrumo/application/aggregation/oss_ioss.py` [tui], `src/cadrumo/application/auth/operation_definitions.py` [tui], `src/cadrumo/application/auth/operator.py` [tui], `src/cadrumo/application/modelo/calculation_actions.py` [tui], `src/cadrumo/application/modelo/operation_definitions.py` [tui], `src/cadrumo/application/modelo/verification_actions.py` [tui], `src/cadrumo/application/modelo/work_review.py` [tui], `src/cadrumo/application/modelo/workspace_models.py` [tui], `src/cadrumo/application/workbench_generation.py` [tui], `src/cadrumo/core/errors/registry/_core.py` [tui], `src/cadrumo_harness/mcp/server.py`

The largest hunks are `tui/launcher.py` (about 1,650 conflicted lines), the four `common.yml` files (about 830 each), `_modelo_aggregate_cli.py` (about 540), the `connect-an-agent.po` files (340–370), `tui/installed_session.py` (about 310) and `application/modelo/operation_definitions.py` (about 290).

## Recommended sequence

1. Get the remaining decision first: provisioning (cluster 3). Auth, locales and sequences are already decided (see Operator decisions). Then write the architectural-intent overview for cluster 1 before touching code.
2. Wait for the MCP worktree's session to commit its checkpoint. `git merge` refuses while overlapping uncommitted edits exist, and those edits belong to another session. Do the same for the TUI: uncommitted TUI work is not in the PR.
3. **Pre-merging `origin/main` is not recommended.** Its payoff is much smaller than it looks. Simulating it (resolved `-X ours` or `-X theirs`) and then landing the TUI still leaves 74 or 63 conflicts, not about 54. The launcher, all four `common.yml` and `hu/errors.yml` would be resolved twice, because "unmarked" in the list above does not mean only `main` touched the file. If the operator wants it anyway:
   - take the cluster 3 decision first;
   - in that same merge, port the `aggregate_public` field, the shutdown release and the browser channel.
4. After the TUI PR lands, merge `main` into `feature/mcp`. Resolve in this order:
   - vault;
   - provisioning;
   - auth onto the MCP path;
   - application/modelo operation definitions, starting with the lifecycle door and edit contract;
   - composition roots;
   - the remaining cluster 1 cases, one at a time against the overview, with one writer per coupled surface;
   - CLI;
   - locales: union, deleted-key guard, then the register pass;
   - publish the authority;
   - regenerate every surface in cluster 6, the env reference after `config.py` and `docs/_sequences` last.
5. Re-check the result with three scans; the import scan alone is not enough:
   - the import scan: every cluster 1 symbol resolves and the deleted modules stay deleted;
   - a field, keyword-argument and method scan for constructor and call sites;
   - a literal grep of every deleted locale key.

## Verification gates (narrow first, then broaden; stream output to disk; rerun failures by test ID)

`just check-code`, `just check-types`, `just check-import-boundaries`, `just check-locales`, `just check-docs-api`, `just docs-sequences-check`, `vaultspec-core vault check all`, `just test-tui`, `just test-cli`, `just test-unit`, then the integration and packaging families that cover the local runtime and the MCP harness. The CLI/TUI parity acceptance named in the profile-access ADR (create in CLI and inspect in TUI, revoke in one and refuse in the other, and so on) is the behavioral check for cluster 1.

## Reproduce or refresh the map

From any worktree of this repository (writes objects only; touches no working tree):

```powershell
git merge-tree --write-tree --name-only --messages feature/mcp feature/tui          # committed-only surface
$fm = git commit-tree "feature/tui^{tree}" -p origin/main -m "simulated squash"     # squash-landing simulation
git merge-tree --write-tree --name-only --messages feature/mcp $fm
git merge-tree --write-tree --name-only --messages feature/mcp origin/main          # main-only share
```

To include a worktree's uncommitted state, copy its index to a temporary file, set `GIT_INDEX_FILE` to that copy, run `git add -A` and `git write-tree`, then `git commit-tree <tree> -p HEAD`. Never use stash for this.
