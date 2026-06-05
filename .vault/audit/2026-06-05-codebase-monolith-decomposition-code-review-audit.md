---
tags:
  - '#audit'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
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

Verification covers Ruff, compileall, 100 focused amendment/import/export/filing tests, 115 focused filing/verification/source-mesh tests, 114 focused modelo CLI tests, public and legacy facade smoke imports, a private-submodule consumer scan across entrypoints/adapters/domain, and direct line-budget confirmation that `_actions.py` is 258 lines. The repository-wide size-budget gate still reports unrelated overview and config callable offenders, so that residual risk remains tracked outside the modelo closure.

## REVIEW-014 | LOW | No blocking findings in live IVA remote-state extraction

Reviewed the W03.P11 `S121` and `S122` live package root decomposition. IVA compensation history, IVA wallet capture/reconciliation, combined IVA remote-state acquisition, acquisition manifest persistence, redaction helpers, and live-surface timeout helpers now live in `_iva_remote_state.py`; `aeat.application.live` remains the public facade and retains compatibility aliases for existing tests. The extraction keeps live-read authentication, active-profile storage, secure-object persistence, and calculation-observation policy in the application layer.

Verification covers Ruff, compileall, 39 focused application live tests, 36 focused CLI live tests, line-budget confirmation for `__init__.py` at 338 lines and `_iva_remote_state.py` at 1018 lines, and a private live-submodule scan across entrypoints/adapters/domain. The scan found only existing test imports, not production consumers.
