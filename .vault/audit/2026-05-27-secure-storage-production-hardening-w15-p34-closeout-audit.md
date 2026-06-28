---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-05-27'
modified: '2026-05-27'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# `secure-storage-production-hardening` W15.P34 Closeout

W15.P34 closes the traceability gap for the pushed W15 storage-hardening commits and records the remaining production blockers after the repair privacy, runtime routing, and namespace-registry waves.

## Accepted Storage Hardening Baseline

| Area | Accepted state |
|---|---|
| Deprecated config-init surface | The repair privacy contract is grounded on the current `config repair` surfaces: list, integrity objects, quarantine, logs, reset-state, profile, registry, and connectivity. Retired `config repair integrity attribution` and `config repair plan` assumptions are no longer accepted. |
| Repair privacy | Repair list, unreadable inventory, quarantine preview, quarantine mutation, bootstrap repair, and repair logs are covered by real encrypted custody roundtrips and redaction tests. Natural object keys, active bucket identifiers, tax-id canaries, and payload content are not emitted through those repair outputs. |
| Runtime routing | Repair integrity, diagnostics quarantine, secure-bound repositories, and active-bucket storage helpers route through centralized runtime factories instead of direct default repository construction. Active-bucket session failures are surfaced instead of hidden behind fallback repository creation. |
| Test isolation | Database-backed storage tests use centralized settings overrides, explicit engine disposal, active-profile bucket helpers, or injected real repositories. Literal passphrase callbacks and naked process-default repository state are guarded. |
| Storage hierarchy | Bucket layout names, keystore paths, wrapped bucket DEK filename, blob/secret schema versions, attachment namespaces, application namespace strings, object-key grammars, and sensitivity classes are represented by typed registry definitions. |
| Application enrollment | Workflow, user profile, repair decisions, live snapshots, filing history, apoderado, ledger rules, filing observations, IVA wallet decisions/events, and IVA compensation history derive namespace/schema/sensitivity values from registry definitions. |

## Residual Blockers

| Blocker | Required follow-up |
|---|---|
| Domain and adapter namespaces are registered but not fully consumed. | Execute the W03 namespace-registry wave to replace remaining domain-level namespace, catalogue, draft, submission, justificante, invoice, transaction, usage-ratio, and modelo work-unit literals with registry entries. |
| Repair policy metadata still depends on command-surface heuristics. | Add registry ownership metadata through `W03.P06.S26` and enforce completeness through `W03.P06.S27` so diagnostics, repair policy coverage, and repair command routing use registry metadata instead of duplicated command classification. |
| Approved environment guard residuals remain. | Retire the residual inventory incrementally as Settings-backed helpers land for token-directory precedence, observability run directories, CLI environment ingestion/refusal, live-test gating, and low-level SQL substrate tests. |
| Some low-level filesystem-layout tests still assert literal filenames. | Keep literal assertions only where the test subject is the filesystem contract itself; otherwise assert through registry path definitions. |
| Registry completeness is not yet a hard repository-enrollment gate for every secure-storage consumer. | Add a convention guard that rejects new secure-object namespace/schema/sensitivity literals outside the registry and approved low-level contract tests. |

## Intentional Guard Hits

- Explicit database URL construction remains allowed only in low-level SQL substrate tests and real isolation fixtures that route through centralized Settings.
- Direct environment access remains allowed only in Settings boundary tests, token-directory precedence tests, observability migration tests, CLI environment-ingestion/refusal tests, and live-test opt-in gates identified in the residual guard inventory.
- Default `SecureObjectRepository` construction is intentionally constrained to runtime-owned factories and approved low-level tests.
- Active-bucket repair surfaces intentionally open repair sessions before resolving repositories, including bootstrap-exempt list and quarantine paths.
- Secure-bound repository tests intentionally exercise route/session mismatch failures so bucket binding cannot silently fall back to process-default storage.
- Repair list and quarantine surfaces intentionally disclose HMAC lookup digests or quarantine metadata while withholding natural object keys, active bucket UUIDs, payloads, and tax-id canaries.

## Required Review Follow-Up

- Re-run code review after W03 namespace-registry enrollment removes the remaining domain and adapter namespace constants.
- Review repair-policy metadata once it moves into registry definitions, with particular attention to command surfaces that can read, mutate, quarantine, export, or recover encrypted records.
- Review any new pragma or noqa added near storage, settings, repair, CLI, or locale boundaries. Suppressions must explain a real static-analysis limitation and must not hide root-cause defects.
- Review localization work through `python -m aeat.locales`; user-facing repair/config errors must continue to use `tr()` and core AEAT exception base classes.
- Review every new storage test for non-tautological behavior: tests must exercise real code paths and must not mirror business logic, mutate code with monkeypatching, or rely on fakes, mocks, stubs, skips, or xfails as shortcuts.

## Closeout Assessment

W15.P31 through W15.P33 materially improved the secure-storage API: repair privacy is tested through real custody, runtime repository routing is centralized, storage path and namespace shape is typed, and migrated application repositories now consume registry definitions. The remaining risk is architectural enrollment breadth rather than a single isolated defect: new or existing storage consumers can still drift unless the W03 registry work turns the current registry into an enforced boundary for all secure-storage namespace, schema, sensitivity, and repair-policy declarations.
