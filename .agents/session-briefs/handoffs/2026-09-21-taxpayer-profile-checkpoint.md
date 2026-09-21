# Taxpayer profile implementation checkpoint

Status: partial. Session `taxpayer-profile`, PROFILE-01 revision 0.1, session-policy revision 1.7, ACCEPTANCE-01 revision 1.6. Provider: Codex. Provider-assigned lead identifier, cc number, and UUID remain pending. Source state: HEAD `c3de61048917269dada80d30f738bae42608c3b5`; preflight anchor `f72ef01f760f87bbe36e83016ed6393921335090`.

## Discovery and ownership

Two bounded Luna Max attempts did not return a report and were stopped. The vaultspec-rag service could not start because its tool interpreter has no supported accelerator; no shared-tool repair, local-index fallback, or manual reindex was attempted. Under session-policy 1.7 this is a discovery-route capability gap. The lead continued from the brief's retained source maps and targeted reads only.

The anchor-to-HEAD and working-tree path filters found no changes under the profile domain/application packages, CLI profile configuration, TUI profile/app/registration surfaces, or `dev/acceptance`. Current dirty TUI work is in `entrypoints/tui/launcher.py` and Modelo workspace modules and remains outside this session's ownership. Income, IVA, assets, calendar, persistence namespace, and Modelo files have active peer changes. PROFILE-01 must not touch those overlapping files without fresh coordination. No test reservation exists yet.

## Bounded filing-critical field matrix

This is the autonomo path plus contrast fields needed to locate actual writer/consumer gaps. `CLI` means the shared setup/edit wizard projection; `TUI` means the schema-driven Account Profile manager. Both ultimately use canonical profile fact validation and encrypted record persistence. Collection support is recorded separately because a visible schema row is not proof of usable row creation/removal.

| Canonical path | Meaning/type | CLI writer | TUI writer | Consumer/readiness | Current limitation |
| --- | --- | --- | --- | --- | --- |
| `identity.tax_id` | legal identity/string with canonical identity validation | `tax-id` | scalar editor | identity guard, filing profile binding | representation authority is separate |
| `taxpayer_type.entity_type` | natural/legal/attribution enum | `entity-type` | choice editor | conditional setup and applicability | supported contrast set must be tested |
| `tax_residence.ccaa` | residence jurisdiction enum | `tax-residence-ccaa` | choice editor | regional income rules/readiness | not a fiscal-address substitute |
| `censo.activity_start_date` | ISO date | `activity-start-date` | typed scalar validator | deadlines and cross-period calculation gating | projection is current-only, not as-of history |
| `activities.{n}.*` | repeatable activity row | wizard activity surface is incomplete for the accepted row model | rows render, but row creation/removal is unproven | activity/applicability and filing selectors | multi-row writer parity requires reproduction; governing activity ADR is not accepted |
| `irpf.estimation_regime` | IRPF regime enum | wizard choice | choice editor | income applicability/bindings | conflicts and effective dating need tests |
| `iva.regime` | IVA regime enum | `iva-regime` | choice editor | Modelo 303 applicability/readiness | preference cannot override legal applicability |
| `withholding.has_employees` | boolean obligation driver | `has-employees` | boolean choice editor | retenciones readiness | false must remain distinct from unobserved |
| `withholding.pays_professionals_with_retencion` | boolean obligation driver | `pays-professionals-with-retencion` | boolean choice editor | Modelo 111 readiness | clear/unset behavior requires proof |
| provenance and source metadata | source/validity windows | imported or application-owned, not raw operator JSON | displayed through overview where projected | reconciliation and audit | event history is not reconstructable fact history |

Imported-only census evidence remains limited to the existing reviewed reconciliation mapping. Derived fields are not editable. Secrets and representation records are owned outside profile facts. The certificate byte parser remains an explicit unsupported/refusal path.

## Representative fact trace

`censo.activity_start_date` is declared by the profile schema at `src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml:383-389`. The shared wizard binds `activity-start-date` to that canonical path at `src/cadrumo/application/wizard/catalogue.py:661-662`, and CLI create/edit exposes the field from `src/cadrumo/entrypoints/cli/config/profile_command_specs.py:280`. The TUI manager persists the selected schema path off-loop at `src/cadrumo/entrypoints/tui/profile/overview.py:865-900`; installed composition injects the application write door at `src/cadrumo/entrypoints/tui/installed_session.py:106-121`.

The canonical writer trims or explicitly clears the value and publishes through one validated fact-change path at `src/cadrumo/application/user_profile/fact_write.py:69-136` and `:169-190`. It validates the whole next fact set, compares effective values for no-op behavior, and calls the authenticated `ProfileRecordRepository.apply_fact_changes` CAS boundary. The encrypted record repository loads and updates at `src/cadrumo/application/user_profile/profile_record_repository.py:373-378` and `:457`; its accepted decision binds it to the profile-local secure-object database.

The current projection parses the canonical value into the deadlines taxpayer profile at `src/cadrumo/domain/deadlines/profiles.py:413`. Calculation continuation reads the same wizard-free profile projection at `src/cadrumo/application/calculations/relation_prefill.py:396-416`, and the deadline engine gates pre-activity obligations at `src/cadrumo/domain/deadlines/engine.py:99-115`. This proves one shared input-to-consumer route in source, not installed-runtime acceptance.

## Initial PROFILE-01 outcomes

PR1-PR12 are not exercised. Source evidence supports existing shared writers, encrypted persistence, CAS, current projection, and registered frontend doors, but none is promoted to installed acceptance. PR6 historical resolution and production filing snapshot pinning remain unsupported/undetermined. PR7 real certificate ingestion is blocked on grounded document-layout evidence. Live access is blocked by scope.

## Next bounded actions

- P01.S02: add exact synthetic reproductions for explicit clear versus older dated value, stale CAS writes, in-flight user switch, census precedence, and representative typed TUI editors. Reserve only the selected nodes before running them.
- P01.S03: inspect current filing/profile snapshot callers and calendar ownership, then issue a decision packet if earlier-period evaluation cannot be expressed without new temporal semantics.
- Do not edit dirty Modelo, persistence namespace, launcher, or tax-lane files until their active owner confirms transfer or a disjoint insertion point.

## Verification reservations

- Owner `taxpayer-profile` / root; reserved 2026-09-21; status queued: direct clear-after-dated-value projection probe using synthetic `UserProfileFact` values only.
- Owner `taxpayer-profile` / root; reserved 2026-09-21; status queued: `uv run pytest -n 0` for `test_effective_window_end_is_reported_not_enforced.py::test_a_closed_window_still_projects_its_value`, `test_profile_edit_verb.py::test_a_blank_optional_flag_clears_the_fact_and_records_one_change`, `test_pointer_transition_authority.py::test_real_child_a_to_b_to_a_advances_every_transition_and_refuses_stale_aba`, `test_censo_pull_verb.py::test_a_clear_and_a_value_conflict_raise_separate_notices`, `test_manager_field_editors.py::test_a_date_box_says_which_layout_it_wants`, and `test_app.py::test_change_user_returns_typed_identity_and_revokes_old_profile_root`. No aggregate lane is reserved.

## P01.S02 reproduction results

- Explicit clear after an older dated value: **failed/reproduced**. A temporary exact regression asserted that a 2021 `value=None` fact removes `contact.postcode` after a 2019 value. `record_to_path_values` returned `28001`; pytest exited 1 with 1 failed. Sanitized run metadata: `20260921T152855.776195Z-pytest-30676-c63fa612/run.json`. The temporary test was removed; the permanent test must land with the P02 projection fix.
- Stale selection/CAS foundations: **proven at focused unit level**. Pointer A-to-B-to-A stale ABA refusal passed. `ProfileRecordRepository.apply_fact_changes` independently compares expected revision and digest before replacement; a profile-switch-specific in-flight integration remains missing.
- Entity switching: **partial**. The focused TUI handover test passed and proves a successful F5 outcome revokes the old composed catalogue/search root and returns the new immutable profile identity. It does not start a profile write before F5, so the brief's in-flight-write transition remains not exercised and is assigned to P03.S07.
- Census precedence and clear visibility: **proven at focused entrypoint level**. The exact CLI notice test passed: an explicit clear and an ordinary value conflict remain separate outcomes. Source inspection confirms reconciliation consumes `record_to_effective_facts`, so it sees the latest clear and does not share the value-projection defect.
- CLI clear and TUI date usability: **proven at focused entrypoint level**. CLI blank optional edit persisted an explicit clear and one change; the TUI date editor exposed the required date layout. Collection row creation/removal, numeric units, and installed continuation remain not exercised.
- First reserved command selected three unit nodes and deselected the three integration nodes under the repository default marker expression: 3 passed, 3 deselected, exit 0, metadata `20260921T152912.909723Z-pytest-17540-4811be5e/run.json`. The explicit `-m integration` follow-up ran the three previously deselected exact nodes: 3 passed, exit 0, metadata `20260921T152929.219311Z-pytest-56856-ee8dfe50/run.json`.

Reservations above are released. No aggregate gate or shared external resource was used.

## P01.S03 historical-context decision packet

Status: **blocked for implementation; audit complete**.

Conflicting contract: profile facts carry `valid_from`/`valid_to`, immutable COMPLETE-only `UserProfileSnapshot` values exist, and an encrypted `ProfileSnapshotPersistencePort` exists. However, targeted production-source search found no caller of `create_user_profile_snapshot`, `UserProfileSnapshot.from_profile`, or `profile_snapshot_persistence` outside their definitions/adapters. `application/modelo/profile_binding.py:1580-1601` loads the authenticated current `ProfileRecordRepository` whenever no test override is supplied. Its subsequent derived-family work uses the filing year but still starts from today's selected record. `record_to_path_values` and `profile_fact_index` have no `as_of` parameter and deliberately ignore `valid_to`.

Calendar plan P01.S02 now owns explicit evaluation-date threading through historical applicability. That work does not establish historical profile resolution or filing-time profile pinning. PROFILE-01 cannot change the same meaning independently, and a new profile snapshot store is explicitly forbidden because the existing snapshot type and persistence authority already exist.

Bounded options requiring coordinator/adviser decision:

1. Pin the existing immutable profile snapshot when a filing/declaration context is created and require later calculation/export/review to resolve that snapshot. This best protects persisted filing meaning but changes declaration persistence and lifecycle contracts across tax lanes.
2. Add an explicit `as_of` resolver over effective-dated facts for prospective calculations, while separately pinning the resulting snapshot once a filing context exists. This covers both historical previews and durable filings but threads a new temporal parameter across many callers.
3. Continue current-only profile resolution and expose historical profile context as unsupported. This is the smallest safe near-term behavior but PR6 remains blocked and earlier-period work must refuse rather than silently use current facts.

Impact: options 1 and 2 require an accepted decision and coordinated ownership with calendar plus tax workflow plans. Option 3 requires an explicit capability/refusal surface in later PROFILE-01 Steps but no new temporal architecture. Until decided, no current projection will be relabelled historical, and persisted filings will not be rewritten.

Evidence checks NOT RUN: no filing creation or installed frontend journey was executed for this audit. Existing snapshot unit tests prove canonical construction/refusal only, not production pinning.

## P02.S04 verification reservation

- Owner `taxpayer-profile` / root; reserved 2026-09-21; status complete/released: exact projection regression plus the owning effective-window file and relation-prefill activity-start consumer passed 8 tests, exit 0, metadata `20260921T153550.328112Z-pytest-46628-1d698dde/run.json`. Explicit integration selection for CLI clear and census clear precedence passed 2 tests, exit 0, metadata `20260921T153607.685354Z-pytest-50184-efcd11a7/run.json`. `ruff check` and `ty check` passed both touched files. No aggregate lane or shared external resource was used.

P02.S04 outcome: **fixed**. The canonical effective-fact map now resolves the latest dated fact including an explicit clear before value projections omit nulls. Path values, selector values, and the typed Modelo profile-binding index can no longer resurrect an older value; the provenance projection continues to expose the clear itself.

## P02.S05 verification reservation

- Owner `taxpayer-profile` / root; reserved 2026-09-21; status complete/released: exact snapshot canonicality, required profile event emission, real-path scalar profile binding, absent-fact anti-tautology, and profile export identity nodes passed 5 tests, exit 0, metadata `20260921T153757.875818Z-pytest-8680-a35e2a3a/run.json`. No persistence namespace edit, aggregate lane, or external resource was needed.

P02.S05 outcome: **proven for the changed projection boundary**. Canonical snapshot construction/refusal, required event-emitter coverage, typed real-path Modelo bindings, absent-fact handling, and profile-derived export identity remain green. This does not promote dormant production snapshot pinning to supported; PR6 remains blocked as recorded above.

## P03.S06 CLI usability audit

Status: in progress. Actual `uv run aeat` help was exercised from source. `config profile` exposes create, edit, view, validate, complete-setup, delete, list, status, history, capabilities, census, descendants, archive, recovery, and generic `add-row`. Canonical active-profile selection is discoverable under `config login [NAME]`, whose help identifies UUID or exact label and the already-selected fallback. `profile edit --help` exposes typed boolean pairs, enum choices, date format guidance, units for turnover, repeatable income-category flags, and the obligation-driving autonomo fields.

Confirmed gap: the generic repeatable-section lifecycle only has `add-row`. Source search found no generic `edit-row` or `remove-row` frontend, even though `section_rows.py` owns atomic indexed creation and `apply_profile_fact_changes` already owns exact clears. The TUI renders indexed rows but likewise has no row creation/removal door. Therefore PR3/PR4/PR5/PR10 cannot be marked proven for activities or other repeatable sections. The next implementation slice must add application-owned update/remove operations and project them into both frontends without relying on the unaccepted multi-activity ADR or redefining row identity.

P03.S06 outcome: **CLI lifecycle complete**. The application row owner now supplies add, partial update with omission-versus-explicit-clear semantics, and removal through the canonical whole-record validator and encrypted revision/digest CAS. Row keys come from the existing schema projection; `base` names the unindexed row and numeric identities are stable. Clear tombstones remain in the record and row allocation now treats their paths as retired identities, preventing an old row reference from targeting a later add. The installed CLI exposes `add-row`, `edit-row`, and `remove-row` through those shared contracts with typed success/no-op results and localized validation/missing-row refusals. Focused installed-entrypoint coverage passed 3 tests; targeted Ruff and ty checks passed. Historical profile resolution remains blocked exactly as recorded above.

P03.S07 outcome: **TUI row lifecycle and baseline safety implemented**. Profile overviews now project record revision/digest and repeatability. Installed TUI composition binds scalar/add/update/remove callbacks to the authenticated profile and passes the editor-open baseline into the shared application mutations. Repeatable rows have add and confirmed remove affordances; existing row fields update or explicitly clear through the row contract using path-derived stable keys. The worker serializes activation, rejects stale CAS with localized guidance, refuses wrong-profile completions, refreshes only from the persisted projection, and does not describe navigation/cancellation as rollback. The dedicated race suite passed 7 tests; existing manager/account tests passed. Installed-generation composition currently has an unrelated concurrent calendar-fixture failure (`OverviewCalendar.evaluated_on` missing), recorded but not attributed to PROFILE-01. Targeted Ruff and ty passed.

P03.S08 outcome: **frontend copy decoupled and complete for this feature**. TUI add/remove affordances now use TUI-owned `flows.manager.rows.*` keys rather than importing CLI help copy. English, Spanish, Catalan, and Hungarian values were written through the locale authority. The profile/application/flows/TUI domains report complete; the repository-wide locale status remains open only for concurrent assets/modelo keys and unrelated inventory declarations. Focused localization and race regression passed 13 tests.

P03 review correction: the initial integrated review returned REVISION REQUIRED for two high findings. S07/S08 were reopened. Same-profile late results are now discarded when an already-visible revision/digest is newer, with copy that says the save may have completed. The add form uses schema-projected choice controls for closed sets, removal names the exact section and stable row, and success versus no-op is explicit. TUI-owned copy replaced the final CLI diagnostics key. Six direct add/remove/stale/failure tests raised the race suite to 13 passing nodes; combined race, manager, and account coverage passed 29 tests. The remaining post-commit projection-failure distinction is retained as a medium review item for the final integrated review, not presented as proven.

P04.S09 outcome: **installed acceptance harness implemented, not yet promoted to acceptance**. New `dev/acceptance/profile` drivers use four isolated encrypted roots and real installed CLI/TUI child processes for CLI-only, TUI-only, CLI-to-TUI, and TUI-to-CLI lifecycles. They cover fresh-process reopen, clear/removal anti-resurrection, retired identifiers, selector preservation, and sealed archive export/inspect with sanitized receipts. Harness contract tests passed 10 nodes; Ruff, formatting, and ty passed. Actual wheel execution is reserved for S10.

## P04.S10 installed acceptance and gates

Status: **installed cross-entrypoint acceptance proven; repository-wide import gate blocked externally**. The wheel at `var/profile-acceptance/run-20260921-1735/dist/cadrumo-0.5.1-py3-none-any.whl` was installed into a fresh virtual environment and exercised against isolated published authority and four independent encrypted profile stores. The final sanitized receipt is `var/profile-acceptance/run-20260921-1735/journey9/receipt.json`, SHA-256 `2c9d3abe2f5f7dfa1f54684c4517cdd69b2ef77ea826fe1a9c4ac5ce835ab047`; package identity is `bc3cd4df0dae62618bce6d8094b5dbe2b495b8ebeb89a036705761aff603de44` and source identity is `625d777df704b6d2c56a4500b8b2fa698ea5a5d6`.

All four journeys are `proven`: CLI-only, TUI-only, CLI-created then TUI-mutated, and TUI-created then CLI-mutated. The root receipt records `no_op_observed=true`; CLI no-op is derived from the typed `changed=false` response, while TUI-only and CLI-to-TUI require the exact localized visible `flows.manager.edit.no_change` result and reject the ordinary saved result before emitting typed boolean evidence. The journeys also prove modify, explicit clear, removal, fresh-process reopen, retired-row refusal, stable selector meaning, and public sealed archive export/inspect. The TUI child uses the shipped visible login and manager controls; no private-store write substitutes for frontend behavior. Caller-owned encrypted stores and sealed synthetic archives are retained; receipts contain no credentials or profile fact values.

Harness diagnostics before the successful run were not promoted: journey1 used an unpublished authority path; journey2 exposed the integer archive-schema contract; journeys3/4 exposed an off-viewport mouse activation; journey5 exposed missing fresh-process login admission; journey6 exposed missing adapter composition during admission; journey7 lacked auditable TUI no-op evidence; journey8 accepted any successful save message as no-op. Those harness defects were corrected through established public contracts, and journey9 is the final acceptance receipt.

Verification after the final corrections: acceptance harness tests 14 passed (`20260921T185127.912005Z-pytest-72740-c762b045`), including positive exact-no-change and negative saved-result predicates; targeted formatting, Ruff, and ty passed. The combined affected profile selection passed 55 tests (`20260921T180519.980194Z-pytest-43408-e56fbb0c`). A clean detached worktree at `06e5524ce2` produced a stable canonical `just check-import-boundaries` census (`source_snapshot_before == source_snapshot_after`) under run `20260921T184352.815937Z-check-import-boundaries-38580-561c8013`; it still fails on ten shared findings in assets, calendar, income-tax, M303, workbench, quality, and ledger-test files plus the pre-existing `dev.acceptance` lane declaration gap. No PROFILE-01 path occurs. S10 therefore remains open on an external repository-wide gate dependency rather than recording a false pass.

The isolated authority publication was confined to the acceptance run root. The successful publication used the registry authority pipeline underlying the canonical recipe; any further publication must use `just registry-publish-authority` with `CADRUMO_AUTHORITY_ROOT` set to an isolated destination.

## PROFILE-01 acceptance disposition

| ID | Status | Evidence and limitation |
| --- | --- | --- |
| PR1 | not exercised | Installed creation/login works, but the complete first-run and incomplete-setup matrix was not rerun. No manufactured facts were introduced. |
| PR2 | not exercised | Focused switching and stale-result tests pass, but installed acceptance uses one profile per journey and does not prove a real two-entity in-flight F5 continuation. |
| PR3 | proven | Field/writer/consumer matrix, typed shared row mutations, CLI/TUI parity, explicit clear, and stable identities are covered. Scope is the current-profile supported row contract. |
| PR4 | proven | Supported current activity row facts, selector preservation, validation, and nonordinal targeting are covered; unsupported historical applicability is excluded. |
| PR5 | proven | Focused races cover save, no-op, clear, cancel/navigation, invalid input, stale CAS, removal-before-save, repeated activation, and persistence failure; journey9 proves persisted frontend outcomes. |
| PR6 | blocked | Historical/as-of profile resolution and production filing snapshot pinning remain undefined cross-lane decisions. Current records are not presented as filing-time snapshots. |
| PR7 | blocked | Synthetic census clear/conflict behavior is focused-test proven, but real certificate ingestion remains blocked on grounded document-layout/specimen evidence. |
| PR8 | proven | Affected typed Modelo binding tests and the public sealed profile archive consumer retain current-profile meaning; full tax-lane recalculation was deliberately reused rather than rerun. |
| PR9 | not exercised | Receipts and failures are redacted and local credential admission is covered; live AEAT authentication/representation authority was out of scope. |
| PR10 | proven | Typed CLI help/results, visible TUI controls, localized refusals, stable targets, save/no-op distinction, and fresh refresh behavior are covered. |
| PR11 | proven | Four independent installed journeys prove CLI-only, TUI-only, and both sequential continuations after fresh-process reopen. |
| PR12 | proven | The journeys use encrypted caller-owned stores, schema validation/refusal, stdin-only generated credentials, and sealed exports with no plaintext fallback or private-store shortcut. No migration redesign was touched. |

## Target-branch delivery audit (2026-09-21)

Target: `Y:\code\cadrumo-worktrees\tui-modelo`, actual branch `tui/modelo`. Bounded provenance inspection found no detached-only PROFILE-01 implementation and no dirty PROFILE-01 product or acceptance files in the registered detached worktrees. The retained detached snapshot at `C:\Users\hello\AppData\Local\Temp\assets-tui-installed-b08f1b79a8-20260921\source` is HEAD `06e5524ce2`; it is not the delivery destination and was not deleted.

| Change/commit | Current location | Already present in target? | Required integration action |
| --- | --- | --- | --- |
| S01-S05 `009c059c1e`, `1326498730`, `c21bb7e830`, `2efd71ccb5`, `c8e97d92ea` plus reviews | `tui/modelo` history | yes | none |
| S06-S08 `33bf13c174`, `0651476765`, `e8ec6f0558`, `742a912049` | `tui/modelo` history | yes | none |
| S09-S11 `e18409a5da`, `5bb58620b0`, `06e5524ce2`, `a375bccb74`, `26ba3fd5b3`, `d298d2f544` | `tui/modelo` history | yes | none |
| Delivered-tree CAS test typing `474f52f6b0` | `tui/modelo` history | yes | committed in target |
| Journey9 receipt | ignored target `var/profile-acceptance` | yes; SHA-256 `2c9d3abe2f5f7dfa1f54684c4517cdd69b2ef77ea826fe1a9c4ac5ce835ab047` | retain in place; do not commit runtime artifacts |

Target-tree verification at `474f52f6b0` and descendants: 27 selected profile/acceptance/TUI tests passed, 3 CLI integration tests passed, and 2 acquisition integration tests passed; targeted Ruff and ty passed. The single coordinated canonical `just check-import-boundaries` run `20260921T202726.929353Z-check-import-boundaries-33808-7c6f29ec` exited 7 with the established ten external findings and a changing governed source snapshot, so it is not a pass. The earlier stable detached canonical run `20260921T184352.815937Z-check-import-boundaries-38580-561c8013` isolates the same external findings and no PROFILE-01 path. S10/S11 remain open pending repository gate resolution. Other lanes' dirty files, including the active `launcher.py` edit, were untouched.

## Stable integrated gate window and correction packets

Because active income, IVA, retenciones, assets and TUI lanes continued writing the target, the verification source was an immutable detached worktree at `Y:\code\cadrumo-worktrees\tui-modelo-profile-gates-20260921`, commit `1f0761810f259821f887dc5e3bbe826774789423`, with `uv sync --frozen` (CPython 3.13.11, 227 locked packages). The target remained `tui/modelo`; its unrelated uncommitted changes were not copied into the snapshot. The import gate's before/after source digest matched `29c838b6bbb7f2fbc3a03a0493a4c25b39c4bc4d32c9e7ce427b153ee9330aef`. Later target commits, including PROFILE-01 correction `fb16a14545` and generated-inventory correction `1be9f352f5`, are *not* covered by these snapshot results.

| Canonical command | Snapshot scope | Exit/result | Current owner packet |
| --- | --- | --- | --- |
| `just check-import-boundaries` | Whole governed graph, run `20260921T210158.548162Z-check-import-boundaries-59212-3ec3b1e1` | 7; stable source, graph authority unavailable | Missing `dev.acceptance` layer, 13 subordinate-only modules under `dev/acceptance/assets`, stale M303 load target, 8 hard diagnostics and 10 unapproved ratchet edges. `fb16a14545` corrects the layer; `1be9f352f5` regenerates target inventories. Remaining owners below. |
| `just check-style` | Repository Ruff | 1; 9 findings | Packaging test unused imports (2), registry XSD docstring (1), assets persistence test import order (1), retenciones binding long lines (5). |
| `just check-format` | Repository Ruff | 1; 45 files | Assets, income, IVA, retenciones, calendar, Modelo, TUI and profile. Five PROFILE-01-related files were formatted and committed in `fb16a14545`; the other files stay with their lane owners. |
| `just check-types` | Full ty plus configured pyrefly/basedpyright production subsets | 1; 183 diagnostics (173/3/7) | Income/shared export 90; IVA 24; retenciones 19; assets 9; calendar 12; TUI/Modelo shared 28; Modelo readiness 1. The only PROFILE-01-touched type finding was the missing `OverviewCalendar.evaluated_on` fixture, fixed and tested in `fb16a14545`. Full detail: `.logs/audit-runs/2026-09-21/20260921T211044.270845Z-audit-types-64268-7c0ce940/run.log` in the snapshot. |
| `just test-gate origin/main` | Change scope too broad, documented fixed contract set; CI contracts and harness | 0; 966 parallel, 3 serial, 1 perf, 4 harness passed | No failure at checked snapshot. Target commits after `1f0761810f` require proportionate revalidation. |

The stable import report's complete diagnostics are at `.logs/test-runs/2026-09-21/20260921T210158.548162Z-check-import-boundaries-59212-3ec3b1e1/artifacts/import-health.json` in the snapshot. Required owner corrections, without suppressing the detector:

| Failed invariant | Exact source/symbol | Owner | Correction/verification |
| --- | --- | --- | --- |
| Closed dev classification | `.importlinter` omitted `dev.acceptance` | PROFILE-01/shared quality | Classified it, kept `exhaustive = True`, detector negative/positive tests passed. |
| Graph/subordinate census | 13 `dev/acceptance/assets/**/*.py` modules absent from Grimp because `assets/__init__.py` is absent | ASSETS acceptance | Add inert package marker; rerun full import census and detector regression. Do not exclude files. |
| Stale dynamic load target | `dev/quality/metadata/{application_entrypoint_modules,import_load_targets}.json` names deleted `_m303_filing_evidence_input` | PROFILE-01/shared quality | Regenerated both from current source; inventory checks and three loadability fixture tests passed. |
| Application inward (5 edges) | `application/aggregation/tests/test_withholding_producer.py` concrete persistence imports | RETENCIONES/aggregation | Move concrete integration assertions to persistence or inject ports/fakes; rerun import and owning tests. |
| Application inward (4 edges) | `application/modelo/tests/test_m303_ordinary_filing_evidence_authoring.py` concrete attachment/profile test support | IVA/Modelo/persistence | Move concrete integration assertions to persistence or use inward ports/fakes. |
| TUI/CLI sibling boundary | `entrypoints/tui/ledger/tests/test_actividad_asset_parity.py` imports private CLI asset adapter | ASSETS/TUI | Test shared application operations without sibling adapter import. |
| Private cross-package symbols (2) | `dev/acceptance/assets/export_journey.py:20` imports `_ingest`, `_result` | ASSETS/income acceptance | Publish a semantic acceptance helper at its defining owner and consume it directly. |
| Private cross-package module | `dev/acceptance/calendar/tests/test_parity.py:29` imports CLI `_overview_rendering` | CALENDAR/CLI | Move reusable renderer to public canonical owner. |
| Private cross-package module | `dev/acceptance/income_tax/authority.py:19` imports filing `_export_parity` | INCOME/application filing | Move reusable validator to public canonical owner. |
| Canonical import definition | `application/workbench_generation.py:803` reexports `ModeloHistoryPorts` | INCOME/Modelo application | Import directly from `modelo.history_ports`. |
| Private cross-package symbol | `entrypoints/cli/tests/test_m303_ordinary_calculate_cli.py:21` imports `_iva_transaction` | IVA/aggregation | Move test factory to public owning support module. |

These are assigned correction packets, not claims of current gate success. No owner-confirmed lease exists yet for other lanes' active files. The package-marker owner was requested asynchronously; independent PROFILE-01 and shared-quality corrections continued. Preserve journey9 at its original source/wheel identity; no new authority publication or installed profile run was required by the format/config/test-fixture changes.
