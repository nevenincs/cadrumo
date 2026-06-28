---
tags:
  - '#audit'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# `codebase-monolith-decomposition` Code Review

## REVIEW-001 | LOW | No blocking findings in completed CLI extraction tranche

Reviewed the completed W02.P03 residual extraction tranche covering config diagnostics/apoderado, ledger ratios, live verify, and modelo audit command surfaces. The changes preserve top-level façade exports for moved Typer apps, keep command behavior delegated to application/domain services, and pass the focused real-behavior tests recorded in the step logs.

Residual risks are non-blocking and already recorded in step notes: `test_apoderado_happy_path_against_active_profile` still has an unrelated direct-subapp invocation mismatch, and `_config/_google.py` carries an unrelated one-line worktree change that required its size budget to reflect the current tree.

## REVIEW-002 | LOW | No blocking findings in W02.P05 residual extraction slice

Reviewed the completed W02.P05 extraction slice covering ledger rules, config auth, live expedientes, modelo reconcile flattening, and Google sync calc extraction. The changed roots continue to act as public façades for extracted command apps/functions, the extracted command surfaces preserve existing operator command paths, and behavior remains delegated to application/domain services rather than being newly implemented in CLI roots.

Verification recorded in the step logs covers focused real-behavior tests for ledger rules, config auth, live expedientes, modelo reconcile, Google sync calc/push/error localisation, help probes for extracted command paths, ruff, compile checks, and the global CLI module/command size guard.

Residual risk remains the broader decomposition objective: `_ledger.py` and `_config/__init__.py` are still above 1250 lines and are tracked by open W02 residual rows.

## REVIEW-003 | LOW | No blocking findings in ledger lifecycle and config repair/history tranche

Reviewed the W02.P05 continuation covering ledger lifecycle extraction, UUID-safe ledger fixture repair, config repair/profile verification, root bootstrap normalization for repair recovery, and config bucket-history extraction. The root modules remain façades/registrars; moved command code continues to call application/domain services for storage, repair, and event-history behavior.

Verification recorded in the step logs covers ledger lifecycle behavior, destructive confirmation paths, ledger validation and UX fixture suites, config repair bootstrap behavior, manifest-status repair, bucket-history parsing and custody usage, help probes, static CLI size guards, ruff, compileall, and plan check.

Residual risk is not closed: `_ledger.py` and `_config/__init__.py` remain above the final 1250-line objective, and broader application/domain/backend monolith rows remain open.

## REVIEW-004 | LOW | No blocking findings in modelo, ledger, and live application decomposition slice

Reviewed the completed continuation covering `S53`, `S55`, `S56`, `S57`, `S112`, `S113`, and `S114`. The modelo workflow-gate extraction preserves the `aeat.application.modelo` facade and keeps legacy `_actions.py` compatibility imports for current tests. The ledger application actions root is now a facade over focused action modules, with external consumers still routed through `aeat.application.ledger`. The live root now delegates remote-state DTOs, IVA remote-state outcome/redaction helpers, and filed-data listing helpers to focused modules while preserving `aeat.application.live` public imports.

Verification recorded in the step logs covers focused Ruff and compile checks, modelo action behavior, natural-key modelo CLI UX, ledger application and CLI integration behavior, live IVA remote-state behavior, live filed-data behavior, registry CLI filed-data helper behavior, and live-read CLI subgroup behavior.

Residual risks remain intentionally open: `src/aeat/application/live/__init__.py` is still above the final 1250-line target, and `S115` tracks the remaining filed-data capture orchestration extraction. Broader application, registry, adapter, persistence, and core decomposition rows also remain open.

## REVIEW-005 | LOW | No blocking findings in W02 residual config, ledger, and modelo-test tranche

Reviewed the completed W02.P05 continuation covering profile bundle command extraction, ledger read/discovery/reporting extraction, size-budget ratchets, and the retired `test_modelo.py` split residual. The config and ledger roots remain public command façades; extracted modules are registrars and do not introduce root-module import cycles. The `test_cli_surface.py` fixture repair is valid real-behavior data: the updated and reclassified 121.50 gross row now carries a matching 100.41 + 21.09 tax split instead of violating the gross invariant.

Verification recorded in the step logs covers ruff, command help probes, profile export/import roundtrip and idempotency tests, config boundary tests, ledger command roster, list/review/preflight checks, broader CLI surface/export/UX tests, `test_modelo.py`, and the CLI module-size guard.

Residual risks remain outside this tranche: `_app_live.py`, `_modelo.py`, `_modelo_payloads.py`, and `_ledger_payloads.py` still carry legacy size budgets, and the broader backend/core decomposition waves remain open.

## REVIEW-006 | LOW | No blocking findings in registry binding and schema decomposition slice

Reviewed the completed W03.P07 `S63` through `S66` slice. The registry binding root now acts as a compatibility facade and selector-shape dispatcher over focused invoice, ledger, counterpart, detail-record, withholding, previous-filing, and selector utility modules. The registry schema root now acts as a compatibility facade over scalar, base, formula/parameter, surface, input-kind, and rounding schema modules. Public package imports through `aeat.domain.calculations.registry` remain intact for moved binding and schema classes.

Verification recorded in the step logs covers ruff, compile checks, 83 invoice/counterpart/ledger binding tests, 42 detail-record and selector-shape tests, 338 schema and scalar data-type tests, facade smoke imports, and plan validation.

Residual risks are non-blocking for this slice and already reflected in open plan rows or broad-suite output: the full registry package suite currently has unrelated failures in stale path-gate tests, Modelo 100/200 bound-input fixture drift, registry data-drift gates, workbook parity size baseline, schema hygiene drift, and tautology gates across other modules. These should not be conflated with the binding/schema decomposition, whose focused behavior lanes are green.

## REVIEW-007 | LOW | No blocking findings in SQL secure-object persistence decomposition

Reviewed the completed W03.P08 `S79` and `S80` slice. The SQL secure-object repository remains the consumer-facing facade while row records, revision crypto, schema bootstrap/quarantine DDL, legacy object-key migration, and decryptability diagnostics live in focused private modules. The storage package facade continues to export `SecureObjectRepository` and public secure-object record types; application, entrypoint, and domain consumers do not reach into the new private helper modules.

Verification recorded in the step logs covers RAG grounding, direct import discovery, ruff, compileall, focused SQL secure-object/archive/redaction tests, runtime storage and migrated-repository tests, line-budget confirmation for `secure_objects.py`, and plan validation.

Residual risk is outside this slice: W03.P08 still has open master-key decomposition and verification rows, and the broader repository still contains oversized adapter, application, core, fixture, and test modules tracked by the remaining open plan rows.

## REVIEW-008 | LOW | No blocking findings in master-key bucket-DEK decomposition

Reviewed the completed W03.P08 `S81` and `S82` slice. The provider classes, factory, and activation API remain available through the storage and master-key facades, while bucket-DEK keystore pathing, key-schedule lookup, idle-window resolution, wrapped-DEK serialization, and unwrap-or-mint behavior now live in a focused private helper module. The extraction keeps fail-closed error behavior and the unsecured-mode NIF canary in the master-key activation path.

Verification recorded in the step logs covers RAG grounding, direct blast-radius discovery, ruff, compileall, the full master-key test package, runtime storage and migrated-repository tests, ephemeral-key hygiene tests, public facade import smoke, private-helper consumer search, `_master_key.py` line-budget confirmation, and plan validation.

Residual risks are outside this slice: the next open rows move back to residual application roots, core config/errors, and oversized test/fixture files. The codebase-wide hard size and callable-complexity gates remain open finalization work.

## REVIEW-009 | LOW | No blocking findings in S81/S82 pre-commit master-key review

Reviewed the final pre-commit W03.P08 `S81` and `S82` diff. The public master-key provider classes and factory functions remain in the master-key facade, while bucket-DEK keystore pathing, key-schedule resolution, idle-window lookup, wrapped-DEK document IO, unwrap-or-mint behavior, and the unsecured-backend tax-id classifier now live in focused private helper modules. This preserves storage facade imports and keeps security-sensitive activation behavior delegated to backend storage code rather than leaking into consumers.

Verification recorded in the step logs covers direct import discovery, ruff, 212 master-key tests, 264 storage tests, public facade smoke imports, vault frontmatter and link checks, `_master_key.py` line-budget confirmation at 1241 lines, and plan validation with only the known PLAN022 monotonic-order warning.

Residual risk is outside this slice: the remaining open plan rows still cover oversized modelo/live/overview application roots, core configuration and error registries, oversized fixtures/tests, and final hard size/complexity gates.

## REVIEW-010 | LOW | No blocking findings in residual modelo action split

Reviewed the W03.P11 `S119` residual modelo action decomposition after focused gates exposed and repaired facade regressions for moved action errors and IVA wallet aliases. The package facade still exposes work-unit lifecycle actions, calculation and filing workflows, workflow-period resolution, and legacy action-error classes while the moved implementations live in private helper modules. Registry authority lookup now has one owner in `_registry_resources.py`, with `_registry_helpers.py` delegating to it rather than carrying a duplicate copy.

Verification covers ruff, compileall, direct facade import smoke, and 46 focused modelo application tests. Residual risk remains tracked in the plan: `_actions.py` is still above the final module budget, so follow-up rows `S133` through `S140` now split calculation, verification, filing, amendment, and import workflows.

## REVIEW-011 | LOW | No blocking findings in modelo calculation extraction

Reviewed the W03.P11 `S133` calculation extraction. The public `aeat.application.modelo` facade and legacy private `_actions.py` compatibility path both resolve calculation actions to `_calculation_actions.py`, while shared observation and registry snapshot helpers live in `_calculation_helpers.py`. The extraction keeps binding resolution, IVA wallet decisions, ledger preflight, persistence, and bucket event emission in the application layer; no policy moved to CLI.

Verification covers ruff, compileall, public and legacy facade import smoke, plan validation, and 46 focused modelo application tests. Residual risk remains tracked by the open `S134` verification row and later filing/amendment/import extraction rows because `_actions.py` remains above the final 1250-line budget at 2107 lines.

## REVIEW-012 | LOW | No blocking findings in modelo facade and CLI verification slice

Reviewed W03.P11 `S120` after the public facade import regression was repaired. `aeat.application.modelo` now imports canonical action errors from `_action_errors.py`, work-unit lifecycle actions from `_work_lifecycle.py`, workflow actions from `_actions.py`, and workflow-period resolution from `_workflow_gate.py`, while entrypoint code continues to consume the top-level facade. The CLI test import in `test_profile_export_roundtrip.py` was also corrected to avoid private `_actions.py` reach-through.

Verification covers ruff, compileall, direct facade smoke imports, 46 focused application modelo tests, 134 focused modelo CLI tests, 8 CLI architecture-boundary tests, 4 profile export roundtrip tests, and a private modelo application import scan across entrypoints/adapters/domain returning no matches.

## REVIEW-013 | LOW | No blocking findings in modelo residual action closure

Reviewed the W03.P11 `S135` through `S140` residual modelo action closure. Verification, filing, amendment, and external import workflows now live in focused private modules while `src/aeat/application/modelo/_actions.py` remains a compatibility facade and `aeat.application.modelo` remains the public boundary. The extraction keeps clean-state, IVA wallet, amendment evidence, import custody, supersession, and bucket-event policy in the application layer; no policy moved to CLI.

Verification covers Ruff, compileall, 92 focused application modelo tests, 66 focused import/file/export tests, 36 focused modelo CLI work/export/history tests, 8 architecture-boundary tests, public and legacy facade smoke imports, a private-submodule consumer scan across entrypoints/adapters/domain, and direct line-budget confirmation that `_actions.py` is 258 lines. The modelo production callables in this slice are below the 180-line hard limit. The repository-wide size-budget gate still reports unrelated stale git inventory plus overview/config callable offenders, so that residual risk remains tracked outside the modelo closure.

## REVIEW-014 | LOW | No blocking findings in live IVA remote-state extraction

Reviewed the W03.P11 `S121` and `S122` live package root decomposition. IVA compensation history, IVA wallet capture/reconciliation, combined IVA remote-state acquisition, acquisition manifest persistence, redaction helpers, and live-surface timeout helpers now live in `_iva_remote_state.py`; `aeat.application.live` remains the public facade and retains compatibility aliases for existing tests. The extraction keeps live-read authentication, active-profile storage, secure-object persistence, and calculation-observation policy in the application layer.

Verification covers Ruff, compileall, 39 focused application live tests, 36 focused CLI live tests, line-budget confirmation for `__init__.py` at 338 lines and `_iva_remote_state.py` at 1018 lines, and a private live-submodule scan across entrypoints/adapters/domain. The scan found only existing test imports, not production consumers.

## REVIEW-015 | LOW | No blocking findings in overview calendar extraction

Reviewed the W03.P11 `S123` and `S124` overview root decomposition. Calendar DTOs, event synthesis, filing-evidence merge, applicability filtering, profile completeness warnings, and `build_overview_calendar` now live in `_calendar.py`; `aeat.application.overview` remains the public facade and retains the existing `derive_modelo_applicability` re-export. Status-report advisory helpers remain in the root because they are separate from calendar aggregation.

Verification covers Ruff, compileall, 147 focused overview application tests, 49 focused overview CLI tests, and 26 focused core logging tests. The verification surfaced and repaired a logging-redaction regression where placeholder-bearing sensitive assignments removed the placeholder but left `LogRecord.args` populated. Residual risk remains outside this slice: `src/aeat/application/overview/tests/test_calendar.py` is still oversized and should be handled in a test-surface decomposition row.

## REVIEW-016 | LOW | No blocking findings in modelo internal import cleanup

Reviewed the W03.P11 `S141` modelo import-boundary cleanup. The public modelo facade imports focused action owners directly, and internal helpers now use focused modules instead of reaching through `_actions.py`. `_actions.py` remains as a legacy compatibility facade for tests and private callers, but application-internal code no longer depends on it.

Verification covers Ruff, compileall, direct private-import scan, 26 focused history/selector/work-addressing/source-mesh tests, 30 filing-flow tests, 15 export tests, 36 verification-substance tests, and 8 architecture-boundary tests. `S142` remains open because its global size-budget check currently depends on concurrent uncommitted config/budget inventory work.

## REVIEW-017 | LOW | No blocking findings in config budget and modelo facade closure

Reviewed the combined W02.P10 `S143` through `S146` and W03.P11 `S141` through `S142` closure. Config custody and profile-censo registrars now delegate to focused command-registration helpers while preserving root custody verbs and keeping policy in application services. The retired `config profile switch` surface is removed from command registration, payload schemas, locale help, and lifecycle tests in favor of root `config unlock`. The hard size-budget inventory no longer carries stale modelo allowances or deleted tracked paths.

Reviewed the modelo facade cleanup after focused modules became the implementation owners. `aeat.application.modelo` now imports public symbols directly from calculation, amendment, external import, filing, verification, and IVA-wallet modules; `_actions.py` remains only as a compatibility facade. Production scans across entrypoints, adapters, domain, and non-test modelo modules no longer find `_actions` reach-through or stale `_actions` documentation references.

Verification covers Ruff, compileall, locale audit, public facade smoke imports, private-submodule scans, 142 focused modelo application tests, 121 focused modelo CLI tests, 74 config/profile CLI tests, 10 architecture-boundary and codebase size-budget tests, and plan validation with only the known PLAN022 monotonic-order warning.

## REVIEW-018 | LOW | No blocking findings in residual test-surface split and size guard closure

Reviewed the W05.P12 `S147` through `S149` residual test-surface closure. The overview calendar taxpayer-model/entity-type/no-window regression group now lives in a focused calendar test module, while the original calendar test module retains shared fixtures and core calendar behavior. The declaracion parser synthetic-fixture regression group now lives in a focused parser test module, while the original parser boundary module retains boundary tests and PDF helper functions used by earlier tests.

Verification covers Ruff, compileall, 61 overview calendar tests, 102 declaracion parser tests, the 2-test hard codebase size-budget guard, and plan validation with only the known PLAN022 monotonic-order warning. The split tests preserve real fixture and real calendar behavior; no mocks, skips, xfails, or duplicated production logic were introduced.

## REVIEW-019 | LOW | No blocking findings in censo event boundary correction

Reviewed W02.P10 `S150` after correcting the service wiring boundary. Censo refresh/apply bucket-event payload construction now lives in `CensoSyncService`, but concrete secure-object repository wiring remains in the config CLI composition helper. This avoids a new application-to-adapter factory while still removing duplicated event-authoring policy from the CLI command bodies.

Verification covers Ruff, compileall for user-profile and config modules, profile censo CLI tests, user-profile repository tests, architecture-boundary tests, codebase size-budget tests, and a direct scan confirming the censo service no longer imports `runtime_repository` or `secure_object_repository_for_bucket`.

## REVIEW-020 | LOW | No blocking findings in censo event-enrollment boundary correction

Reviewed W02.P10 `S150`. `CensoSyncService` owns refresh/apply event emission, while the config censo CLI remains the concrete composition point for bucket-scoped storage and bucket-event repositories. The user-profile application facade does not add a storage-wiring factory, so the slice removes duplicated event-authoring policy from the CLI without introducing a new application-to-adapter import.

Verification covers Ruff, compileall, direct application import scans for removed storage wiring, 17 application censo service tests, 11 marker-enabled CLI censo tests, the 2-test hard size-budget guard, and plan validation with only the known PLAN022 monotonic-order warning.

## REVIEW-021 | LOW | No blocking findings in domain error registry and custody split

Reviewed W04.P09 `S85` and `S86` plus W02.P10 `S151`. The domain error registry keeps `_domain.py` as the aggregate facade and moves ordered declarations into three private shards. A direct before/after registry comparison against `HEAD` confirmed all 210 domain entries preserve order and `ErrorCode` payloads. The config custody root now delegates secret-store verbs to `_custody_secret.py` while leaving custody policy in application services.

Verification covers Ruff, compileall, direct registry equality comparison, public registry lookup smoke, 39 focused core error and boundary tests, 106 focused config/custody CLI tests, and the 2-test hard size-budget guard. The broad `src/aeat/core/tests` lane failed on unrelated stale meta-test paths and one external-constant alias assertion; that residual is tracked as W04.P09 `S152`.

## REVIEW-022 | LOW | No blocking findings in justificante generator split

Reviewed W05.P12 `S125`. The committed synthetic justificante regeneration command remains `src/aeat/tests/fixtures/justificantes/_generate.py`, while shared receipt rendering and sidecar writing live in `_generate_base.py`, IVA/pagos-fraccionados corpus fixtures live in `_generate_iva_corpus.py`, and the remaining modelo families live in `_generate_misc_a.py` and `_generate_misc_b.py`.

Verification covers Ruff, compileall, compatibility export smoke, 23 focused fixture/provenance tests, the 2-test hard size-budget guard, and vault frontmatter/link checks. No fixture PDFs were regenerated or changed in this slice.

## REVIEW-023 | LOW | No blocking findings in ledger action test split

Reviewed W05.P12 `S126`. The ledger action tests now split create, update, lifecycle, import/export, and review workflows into focused modules, with shared setup in `_action_test_support.py`. The modelo file-flow tests now split calculation, event, filing, and verification workflows into focused modules, with registry-backed setup in `_file_flow_support.py`. The shared helpers still provision real secure-object repositories and import production application services directly.

Verification covers Ruff, compileall, 75 focused ledger action tests, 30 focused modelo file-flow tests, and the 2-test hard size-budget guard. The split introduces no fakes, stubs, monkeypatches, skips, xfails, or duplicated application business logic.

## REVIEW-024 | LOW | No blocking findings in auth production and test split

Reviewed W04.P09 `S156` auth sub-surface plus the W05.P12 `S127` auth test split. Authenticator DTOs/protocols now live in `_authenticator_types.py`, Cl@ve Movil pure helpers and failure types live in `_clave_movil_support.py`, and Cl@ve page-driving methods live in `_clave_movil_page_flow.py`. Existing public auth imports and legacy private helper imports remain available through the original modules.

Verification covers Ruff, compileall, 80 focused auth tests, and the 2-test hard size-budget guard. The registry qualname for `_PersistedSessionInvalidError` now points at the moved class, preventing the core error registry from failing closed during import. Broader W04.P09 `S156` and W05.P12 `S127` remain open for the other production and adapter-test surfaces.

## REVIEW-025 | LOW | No blocking findings in application and adapter error registry shard closure

Reviewed W04.P09 `S87` through `S90`. The application and adapter error registry modules now remain as aggregate facades over private ordered shards. The shard files keep declaration order and `ErrorCode` payloads intact, and each aggregate continues to expose `_DECLARED_ERROR_CODES` for the core registry package.

Verification covers Ruff, compileall for `src/aeat/core/errors/registry`, 34 core error tests, registry aggregate smoke checks for application and adapter entries, selected core boundary/output checks, and the hard codebase size-budget guard. Broad core meta-test failures remain tracked separately as W04.P09 `S152`.

## REVIEW-026 | LOW | No blocking findings in declarations-register split

Reviewed W04.P09 `S157`. Declarations-register page-shape diagnostics now live in `_declarations_diagnostics.py`, remote-read guard helpers and cotejo CSV extraction now live in `_declarations_remote.py`, and `_declarations.py` remains the compatibility facade for the existing private test imports and public declarations workflow.

The declarations adapter tests now split into shared support plus focused part modules while preserving real registry-backed fixtures and secure-object isolation. Verification covers Ruff, compileall for the sede adapter package, a declarations facade `__all__` smoke import, 61 focused declarations tests, and the 2-test hard codebase size-budget guard. Broader W04.P09 `S156` remains open for core config and record-design production surfaces, and W05.P12 `S127` remains open for the other adapter test monoliths.

## REVIEW-027 | LOW | No blocking findings in core config and record-design split closure

Reviewed W04.P09 `S152` and the remaining W04.P09 `S156` production surfaces. `aeat.core.config` now keeps settings construction and override behavior in the facade while support enums, storage-route records, default URL/path loaders, and output-language coercion live in `_config_support.py`. The registry record-design facade now keeps extraction/parsing behavior while off-load-path coverage and calculation-completeness derivation helpers live in `_record_design_coverage.py`.

The core external-constants and file-permissions tests now derive the repository root and source paths from the current test topology, so the meta-tests assert the real source files again. Verification covers Ruff, compileall, 95 focused core/meta tests, 41 focused record-design tests, and the 2-test hard codebase size-budget guard. Remaining open work is outside this slice: CLI transport decomposition, non-CLI callable decomposition, and residual adapter/storage test splits.

## REVIEW-028 | LOW | No blocking findings in adapter and storage test split

Reviewed W05.P12 `S127`. The inbound declaracion parser-boundary and verification-chain monoliths now point to focused sibling modules with shared parser/verification support. The SQL secure-object and runtime migrated repository monoliths now point to focused storage test modules with shared real repository setup. Earlier S127 auth and declarations splits remain covered by their focused committed lanes.

The split keeps tests importing production code and real fixtures; no mocks, skips, xfails, or copied business logic were introduced. Verification covers Ruff, compileall, 95 parser-boundary tests, 94 verification-chain tests, 61 outbound declarations tests, 80 focused auth tests, 137 storage repository tests, and the 2-test hard codebase size-budget guard.

## REVIEW-029 | LOW | No blocking findings in registry schema and referential-integrity test split

Reviewed W05.P12 `S128`. The registry schema and referential-integrity monoliths now point to focused sibling modules with shared support modules, while the split modules preserve the existing domain marker and real registry-authority fixtures.

The split keeps validation behavior grounded in production schema and registry authority code. Verification covers Ruff, compileall, 136 focused registry schema/referential-integrity tests, and the 2-test hard codebase size-budget guard.

## REVIEW-030 | LOW | No blocking findings in CLI transport registrar split

Reviewed W04.P09 `S153`. Profile bundle, config repair, ledger read/evidence/classification/review, modelo projection, and IVA wallet registration are decomposed into focused registration helpers or transport modules while business behavior remains in application services. The repair-policy coverage test was updated for the custody secret command module introduced by the earlier custody split.

Verification covers Ruff, compileall, the CLI module-size and hard size-budget guards, 54 ledger classification/validation tests, 18 IVA wallet tests, 21 CLI surface tests, and 33 focused ledger-list/modelo/profile/repair tests. No command verbs or ADR-governed CLI names were changed in this split.

## REVIEW-031 | LOW | No blocking findings in non-CLI callable split

Reviewed W04.P09 `S154`. Google Sheets apply, ledger split/merge, run-context persistence, registry revision-section validation, IVA compensation reconciliation, and Cl@ve fresh-login construction are decomposed into focused helpers while preserving existing public entry points and backend facades. The observability repair keeps caller-supplied run-id validation ahead of any settings/filesystem work, and the replay canonicity test now scans the observability package root after the tests package move.

Verification covers Ruff, compileall, 30 Google Sheets apply tests, 18 ledger split/merge tests, 31 observability context/replay/logging tests, 19 IVA wallet reconciliation tests, 136 registry schema/referential-integrity tests, 51 Cl@ve/auth smoke tests, and the 2-test hard codebase size-budget guard. The review found no blocking issues.

## REVIEW-032 | LOW | No blocking findings in non-CLI callable and hard-budget closure

Reviewed W04.P09 `S154`, `S155`, and `S91`. Google Sheets apply, ledger split/merge, observability context, registry revision-section validation, IVA compensation reconciliation, and Cl@ve login construction now keep public facades short while pushing branch-heavy logic into focused helpers. The hard size guards now use filesystem inventory under `src/aeat` and carry no legacy module or callable allowance maps.

Verification covers Ruff, compileall, 69 IVA wallet/reconciliation tests, 136 registry schema/referential-integrity tests, 7 Google Sheets apply/export tests, 69 ledger/observability/Cl@ve tests, and the 4 hard module/callable budget tests. The observability run-id test still asserts no rejected run id creates a new artefact, while tolerating unrelated fixture setup in mixed pytest processes.

## REVIEW-033 | LOW | No blocking findings in final monolith decomposition gates

Reviewed W04.P09 `S92`, W05.P12 `S129`, and W05.P13 `S130` through `S132`. The final hard guards now inventory filesystem Python files under `src/aeat`, the split adapter/application/registry/fixture surfaces have focused execution records, and plan state is closed through the residual decomposition waves.

Verification covers full Ruff over `src/aeat`, compileall over `src/aeat`, the 4-test hard budget lane, focused S154 behavior lanes, feature plan validation with only the known PLAN022 ordering warning, and clean feature-scoped vault validation. An earlier out-of-scope secure-storage filename drift was corrected before final handoff.

## REVIEW-034 | LOW | Split persistence regression repaired before final handoff

Reviewed the final hard-budget closure after staged and unstaged worktree changes shifted during execution. The only blocking issue found in the reviewed slice was a transient `split_transaction` persistence call that passed the optional input repository parameter instead of the resolved repository. That was repaired before handoff.

Post-fix verification covers Ruff for `src/aeat/application/ledger/_actions_split_merge.py`, 18 focused ledger split/merge tests, and the 4-test hard module/callable budget lane. A later attempted dynamic scoped test command accidentally ran broad collection because the changed Python list was empty after concurrent index changes; those collection errors are unrelated full-tree fixture/conftest issues and are not used as closure evidence.
