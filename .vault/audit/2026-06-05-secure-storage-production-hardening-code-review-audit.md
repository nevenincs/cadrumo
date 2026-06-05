---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-05-secure-storage-production-hardening-W12-P26-S347]]'
  - '[[2026-06-05-secure-storage-production-hardening-w12-p26-s347-review-audit]]'
  - '[[2026-06-05-secure-storage-production-hardening-W12-P26-S355]]'
  - '[[2026-06-05-secure-storage-production-hardening-w12-p26-s355-review-audit]]'
  - '[[2026-06-05-secure-storage-production-hardening-W12-P26-S356]]'
  - '[[2026-06-05-secure-storage-production-hardening-w12-p26-s356-review-audit]]'
---

# `secure-storage-production-hardening` Code Review

## S347-CR-001 | PASS | S347 closeout is scoped to tracking and evidence

Reviewed the S347 diff as `vaultspec-code-reviewer`. The plan updates only close
`AFR-245` and `W12.P26.S347`; the new exec and audit records document the focused IVA
schema verification. No production code or test code changed in this step.

## S347-CR-002 | PASS | Runtime classification is coherent

The reviewed evidence supports `remote-mirror`: `src/aeat/domain/iva/_schema.py`
contains strict domain schema and external legal citation fields, but no persistence,
runtime bucket resolution, SQL route, secret handling, or environment access. No
runtime-default enrollment gap was found for this slice.

## S347-CR-003 | PASS | Quality gates are adequate for a docs-only closeout

Focused ruff, real IVA domain tests, canonical locale audit through
`python -m aeat.locales`, RAG lookup, and vault plan check all ran. The only residual
plan warning is the known document-order `PLAN022` warning and is unrelated to S347.

## S353-CR-001 | PASS | Runtime-default construction is preserved

Reviewed the S353 production diff as `vaultspec-code-reviewer`.
`CalculationRevisionCatalogueRepository` still defaults through
`resolve_modelo_repository_bucket_id` and `secure_objects_for_modelo_bucket`; no direct
SQL repository construction was introduced.

## S353-CR-002 | PASS | Error hardening reduces leakage without swallowing causes

The changed load path keeps `exc_info=True` logging for secure-object integrity
exceptions and adds explicit error logs for classification and envelope-version drift.
Raised `CalculationRevisionPersistenceError` instances now carry a locale key and
structured context rather than raw exception strings. The original exception remains
chained for the caught storage-integrity arm.

## S353-CR-003 | PASS | Tests exercise real encrypted persistence

The new tests write real secure-object payloads through `isolated_runtime_profile` and
then load through the repository under test. They assert typed localized errors for
classification drift and future inner envelope versions without fakes, monkeypatches,
or tautological source mirroring.

## S354-CR-001 | PASS | Filing record closeout is model-only

Reviewed the S354 closeout as `vaultspec-code-reviewer`. The plan update closes only
`AFR-252` and `W12.P26.S354`; the production file itself remains unchanged because it
is a strict data-model surface, not a storage runtime owner.

## S354-CR-002 | PASS | Repository remediation remains correctly tracked

The audit explicitly leaves `src/aeat/domain/modelos/_filing_repository.py` to
`W12.P26.S355`. This avoids masking the repository's runtime and localized-error work
inside a manifest-discovery row.

## S355-CR-001 | PASS | Runtime-default construction is preserved

Reviewed the S355 production diff as `vaultspec-code-reviewer`.
`ModeloRecordCatalogueRepository` still defaults through
`resolve_modelo_repository_bucket_id` and `secure_objects_for_modelo_bucket`; no direct
SQL repository construction was introduced.

## S355-CR-002 | PASS | Error hardening reduces leakage without swallowing causes

The changed load path keeps `exc_info=True` logging for secure-object integrity
exceptions and adds explicit error logs for classification and envelope-version drift.
Raised `ModeloRecordPersistenceError` instances now carry a locale key and structured
context rather than raw exception strings. The original exception remains chained for
the caught storage-integrity arm.

## S355-CR-003 | PASS | Tests exercise real encrypted persistence

The new tests write real secure-object payloads through `isolated_runtime_profile` and
then load through the repository under test. They assert typed localized errors for
classification drift and future inner envelope versions without fakes, monkeypatches,
or tautological source mirroring.

## S355-CR-004 | PASS | Locale scaffold repair is auditable

The locale changes were produced through `python -m aeat.locales scaffold`, refined
through `python -m aeat.locales set`, and cleaned through
`python -m aeat.locales remove`, then validated through
`python -m aeat.locales audit`. The locale CLI repaired existing shared-branch locale
drift that blocked the S355 validation gate.

## S356-CR-001 | PASS | Runtime-default construction is preserved

Reviewed the S356 production diff as `vaultspec-code-reviewer`.
`WorkUnitCatalogueRepository` still defaults through
`resolve_modelo_repository_bucket_id` and `secure_objects_for_modelo_bucket`; no direct
SQL repository construction was introduced.

## S356-CR-002 | PASS | Error hardening reduces leakage without swallowing causes

The changed load path keeps `exc_info=True` logging for secure-object integrity
exceptions and adds explicit error logs for classification and envelope-version drift.
Raised `WorkUnitPersistenceError` instances now carry a locale key and structured
context rather than raw exception strings. The original exception remains chained for
the caught storage-integrity arm.

## S356-CR-003 | PASS | Tests exercise real encrypted persistence

The new tests write real secure-object payloads through `isolated_runtime_profile` and
then load through the repository under test. They assert typed localized errors for
classification drift and future inner envelope versions without fakes, monkeypatches,
or tautological source mirroring.

## S357-CR-001 | PASS | Runtime-owned construction remains centralized

Reviewed the S357 production diff as `vaultspec-code-reviewer`.
`secure_objects_for_modelo_bucket` still delegates to
`secure_object_repository_for_bucket`; it does not construct SQL repositories, parse
routes, or bypass storage runtime readiness checks.

## S357-CR-002 | PASS | Active-profile failures are structured without changing user-facing keys

`resolve_modelo_repository_bucket_id` now attaches reason context for
`blank_explicit_bucket_id` and `missing_active_profile_bucket` while preserving the
existing localized `application.workflow.errors.no_active_profile_bucket` message key
and caller-selected `ModeloError` subclass.

## S357-CR-003 | PASS | Tests use production helpers and runtime gates

The new tests import the production helper and `WorkUnitPersistenceError`, verify the
centralized settings fallback, and exercise the real runtime factory's unready-runtime
rejection path. No fakes, mocks, stubs, monkeypatches, skips, or mirrored business
logic were introduced.

## S358-CR-001 | PASS | Runtime-default construction is preserved

Reviewed the S358 production diff as `vaultspec-code-reviewer`.
`VerificationReportCatalogueRepository` still defaults through
`resolve_modelo_repository_bucket_id` and `secure_objects_for_modelo_bucket`; no direct
SQL repository construction was introduced.

## S358-CR-002 | PASS | Error hardening reduces leakage without swallowing causes

The changed load path keeps `exc_info=True` logging for secure-object integrity
exceptions and adds explicit error logs for classification and envelope-version drift.
Raised `VerificationReportPersistenceError` instances now carry a locale key and
structured context rather than raw exception strings. The original exception remains
chained for the caught storage-integrity arm.

## S358-CR-003 | PASS | Tests exercise real encrypted persistence

The new tests write real secure-object payloads through `isolated_runtime_profile` and
then load through the repository under test. They assert typed localized errors for
classification drift and future inner envelope versions without fakes, monkeypatches,
or tautological source mirroring.

## S359-CR-001 | PASS | Work-unit model remains manifest-discovery only

Reviewed the S359 scope as `vaultspec-code-reviewer`. `_work_unit.py` defines typed
value records, deterministic id derivation, lifecycle state, and catalogue invariants.
It does not instantiate secure-object repositories, resolve active-profile storage,
read settings, inspect environment variables, or perform filesystem IO.

## S359-CR-002 | PASS | Storage ownership is not duplicated

The encrypted `WorkUnitCatalogue` repository remains
`src/aeat/domain/modelos/_repository.py`, already closed under S356 as
`runtime-default`. S359 therefore correctly closes as `manifest-discovery` without
adding a second storage abstraction.

## S361-CR-001 | PASS | Renta substrate remote-provider signal is a false positive

Reviewed the S361 scope as `vaultspec-code-reviewer`. `_substrate.py` defines closed
`StrEnum` catalogues for Renta substrate axes and has no remote-provider calls, mirror
persistence, secure-object construction, active-profile resolution, settings access,
environment access, or filesystem IO.

## S361-CR-002 | PASS | Register provenance is preserved

The plan row is closed without deleting or hiding the original scanner signal. The
closeout documents the `remote-provider` signal as a false positive for a pure
enum/catalogue module.

## S362-CR-001 | PASS | Submission models are not storage or remote owners

Reviewed the S362 scope as `vaultspec-code-reviewer`. `_models.py` defines strict
pydantic records and a submission status enum only. It has no remote-provider calls,
mirror persistence, secure-object construction, active-profile resolution, settings
access, environment access, or filesystem IO.

## S362-CR-002 | PASS | Relocated secure-storage test import was repaired

The focused submission roundtrip gate initially failed because
`domain/submission/tests/test_secure_storage_roundtrip.py` still imported
`...adapters` after being moved under a `tests` package. The import now uses the
correct `....adapters` package depth, and the real encrypted roundtrip tests pass.

## S363-CR-001 | PASS | Submission preflight remains policy-only

Reviewed the S363 scope as `vaultspec-code-reviewer`. `_preflight.py` invokes
injected deadline and auth-provider protocols but does not directly access secure
storage, active profiles, settings, environment variables, filesystem paths, or remote
provider clients.

## S363-CR-002 | PASS | Refusal and exception handling are explicit

Preflight refusal paths use localized `errors.refused.submission_preflight_*` keys with
structured context. Auth-provider describe failures are logged with `exc_info=True`
and chained into `SubmissionPreflightError`, so the cause is neither swallowed nor
exposed as raw operator-facing text.

## S364-CR-001 | PASS | Submission protocols are boundary declarations only

Reviewed the S364 scope as `vaultspec-code-reviewer`. `_protocols.py` declares
structural ports and strict value types. It does not call remote providers, construct
secure storage, resolve active profiles, read settings, inspect environment variables,
or perform filesystem IO.

## S364-CR-002 | PASS | Concrete repository coupling is avoided

`SubmissionRepositoryProtocol` references `ModeloPresentado` and declares the narrow
load/list/iterate surface consumed by domain/application code. It does not import the
concrete `SubmissionRepository` or adapter-layer secure-storage classes.

## S367-CR-001 | PASS | Transaction models are not a manifest-discovery owner

Reviewed the S367 scope as `vaultspec-code-reviewer`. `_models.py` defines strict
pydantic value records, deterministic transaction identifiers, immutable catalogue
validation, and `BucketTransactionRef`. It has no active-profile resolution, storage
runtime inspection, settings/environment access, filesystem IO, SQL access, or
secure-object construction.

## S367-CR-002 | PASS | Transaction persistence is runtime-bound and encrypted

The concrete storage owner remains `TransactionCatalogueRepository`: it binds to a
bucket, resolves the secure-object repository through storage runtime, writes
`TX_BUCKET_NAMESPACE`, and persists `Envelope[TransactionCatalogue]` payloads at
`SensitivityClass.FINANCIAL`.

## S367-CR-003 | FIXED | Anti-drift tests targeted the wrong import package

The focused transaction roundtrip suite initially failed because five anti-drift tests
imported repository constants from the tests package. The imports now target the
production parent package, and the transaction roundtrip suite passes.

## S367-CR-004 | PASS | Locale audit stays canonical

`python -m aeat.locales audit` passes after verifying the intracom operation-type CLI
refusal keys are recognized by the locale scanner. No manual locale YAML edits were
needed.

## S372-CR-001 | FIXED | User-profile schema stat leaked raw OSError

Reviewed the S372 scope as `vaultspec-code-reviewer`. `_loader.py` called `stat()`
before the TOML read helper could wrap filesystem failures. Missing or inaccessible
schema paths now raise `UserProfileSchemaLoadError` with structured context and chained
cause.

## S372-CR-002 | PASS | User-profile schema load errors are localized AEAT errors

`UserProfileSchemaLoadError` remains under the core `AeatError` hierarchy and now
sets `translated_message="errors.fail.fail_user_profile_schema_load"`. No locale YAML
edits were required because the key already exists and `python -m aeat.locales audit`
passes.

## S372-CR-003 | PASS | Loader remains schema-only, not profile storage

`_loader.py` reads the bundled user-profile schema TOML or an explicit caller-supplied
schema path. It does not resolve active profiles, inspect secure-storage runtime,
construct repositories, inspect environment variables, or persist profile data.

## S372-CR-004 | FIXED | Profile registry-contract test import regression

The focused verification suite initially failed because `test_registry_contract.py`
used over-deep relative imports. The imports now target the production modules and the
schema/registry suite passes.

## S373-CR-001 | PASS | User-profile values are not storage runtime code

Reviewed the S373 scope as `vaultspec-code-reviewer`. `_values.py` defines strict
pydantic profile fact, live profile, and snapshot value records plus UUID/hash helpers.
It has no active-profile pointer reads, manifest scanning, storage runtime inspection,
settings/environment access, filesystem IO, SQL access, or secure-object construction.

## S373-CR-002 | PASS | Active-profile and manifest-bucket are semantic signals

The scanner hit lifecycle and bucket vocabulary in model comments and field names.
Those signals describe the persisted domain shape but do not implement discovery or
runtime storage behavior.

## S373-CR-003 | FIXED | Profile repository verification imports regressed

The focused verification suite initially failed because `test_profile_repository.py`
local imports resolved to `aeat.application.adapters`. The imports now use the correct
package depth and the 28-test user-profile verification suite passes.

## S374-CR-001 | PASS | CLI root is the intended bootstrap-custody gate

Reviewed the S374 scope as `vaultspec-code-reviewer`. `entrypoints/cli/__init__.py`
assembles the lazy command tree, resolves profile labels to bucket UUIDs, applies
bootstrap exemptions, delegates write-route authorization to `inspect_storage_write_policy`,
and opens the active bucket session for non-exempt subcommands.

## S374-CR-002 | PASS | Deprecated config init is not exposed

The root CLI module mounts the lazy `config` subtree and current `app` namespace only.
Focused retired-command tests pass, including the guard that retired `config init`
phrases do not leak into runtime surfaces.

## S374-CR-003 | FIXED | Click protected_args deprecation surfaced in bootstrap path

The focused CLI tests passed but emitted a deprecation warning from the public
`ctx.protected_args` property. `_verb_path_from_context()` now prefers `ctx.args` and
falls back to Click 8's internal protected-argument storage without touching the
deprecated public API. The CLI tests pass with `DeprecationWarning` promoted to an
error for `aeat.entrypoints.cli.__init__`.

## S377-CR-001 | PASS | CLI common stays out of manifest discovery

Reviewed the S377 scope as `vaultspec-code-reviewer`. `_common.py` owns CLI transport
helpers, localized parser refusals, and typed repository accessors. It does not parse
bucket manifests, inspect raw SQL routes, read AEAT environment variables, or construct
secure-storage adapters directly.

## S377-CR-002 | FIXED | Renta aggregation invoice repository re-resolved active profile

`_aggregate_filing_inputs()` already resolved the active bucket id for the Renta
aggregation request, but it constructed `InvoiceCatalogueRepository` through the
implicit active-profile default. The helper now passes the resolved bucket id into the
invoice repository, keeping transaction and invoice aggregation inputs bound to the same
profile bucket.

## S377-CR-003 | PASS | Locale and focused validation passed

The `_common.py` change did not add locale keys. `python -m aeat.locales audit`, focused
common helper tests, focused Renta aggregation tests, and selected backend-boundary
integration checks passed.

## S378-CR-001 | PASS | Config CLI facade delegates storage ownership

Reviewed the S378 scope as `vaultspec-code-reviewer`. `_config/__init__.py` currently
routes profile lifecycle, repair, auth, apoderado, bucket-history, import/export, and
Google app registration through application/domain services. Command handlers do not
construct raw SQL engines or direct secure-object adapters.

## S378-CR-002 | FIXED | Config containment paths lacked debug breadcrumbs

Broad exception-to-operator-diagnostic paths now log at debug level through the
centralized logger before emitting redacted/profile-safe CLI output. Covered paths
include repair log tail reads, profile-record repair/status/show failures, invalid
portable profile bundle parsing, and status projection validation fallback.

## S378-CR-003 | PASS | Locale and focused validation passed

The config facade change added no locale keys. Focused `ruff check`, config boundary
tests, repair bootstrap/reset tests, and `python -m aeat.locales audit` passed.

## S379-CR-001 | PASS | Google config remains a ciphertext remote mirror

Reviewed the S379 scope as `vaultspec-code-reviewer`. `_google.py` owns Google OAuth,
Drive folder configuration, sync probes, calc-sheet transport, and secure-object mirror
push. The mirror path obtains encrypted secure-object records from the active-bucket
repository and uploads ciphertext payloads plus namespace manifests through the
outbound storage provider factory.

## S379-CR-002 | FIXED | Sync push limit refusal detail needed localization

The non-dry-run `--limit` refusal prevents partial remote mirror manifests but only
carried an English implementation message. The error now attaches
`cli.config.google.detail.sync_push_limit_requires_dry_run`, locale leaves were added
through `python -m aeat.locales set`, and the sync-push regression test asserts the
projected refusal detail through `tr()`.

## S379-CR-003 | PASS | Locale and focused validation passed

Focused `ruff check`, Google sync-push integration tests, Google error-localisation
tests, and `python -m aeat.locales audit` passed after the localized refusal change.

## S380-CR-001 | FIXED | Plan row referenced retired profile census path

Reviewed the S380 scope as `vaultspec-code-reviewer`. `AFR-278` and `W12.P26.S380`
still referenced `_profile_census.py`, which no longer exists after the censo rename.
The plan now tracks `src/aeat/entrypoints/cli/_config/_profile_censo.py` and closes the
register entry against the live implementation.

## S380-CR-002 | FIXED | Censo event history used ambient active-bucket repository construction

`_emit_censo_event()` already received the resolved bucket id but constructed
`BucketEventHistoryRepository()` through the default active-bucket factory. The censo
event path now passes `secure_object_repository_for_bucket(bucket_id)` into the event
repository, keeping the event catalogue bound to the same profile bucket resolved by
the command.

## S380-CR-003 | PASS | Censo profile CLI stays application-owned

The profile censo CLI resolves active profile state through the centralized pointer and
manifest scanner, delegates censo snapshot/profile operations to `CensoSyncService`,
uses localized `CliRefusedBoundaryError` surfaces for expected refusals, and does not
own raw SQL routes or duplicate censo modelo foundation routing.

## S380-CR-004 | PASS | Locale and focused validation passed

No locale leaves were added. Focused `ruff check`, profile-censo integration tests, and
`python -m aeat.locales audit` passed.

## S382-CR-001 | PASS | Ledger remains an intended active-profile CLI surface

Reviewed the S382 scope as `vaultspec-code-reviewer`. `_ledger.py` remains the
operator-facing active-bucket command surface for transaction management. It obtains
bucket-scoped transaction repositories through shared CLI helpers and passes repository
bucket ids into application services instead of opening raw storage routes.

## S382-CR-002 | FIXED | Ratios extraction carried ambient event repository construction

The shared dirty worktree had extracted ledger ratios into `_ledger_ratios_cli.py`.
That module emitted ratio mutation and censo override-warning bucket events through
default `BucketEventHistoryRepository()` construction. The event paths now pass
`secure_object_repository_for_bucket(bucket_id)` into the event repository.

## S382-CR-003 | FIXED | Ratios extraction regressed localized decimal refusal

The extracted ratios parser had an English-only decimal parsing refusal. It now reuses
`cli.ledger.errors.invalid_decimal`, and the CLI regression asserts the rendered
message through `tr()`.

## S382-CR-004 | FIXED | Censo mismatch warning catch now logs at debug level

`ratios list` intentionally catches `CensoRatioMismatchError` to show persisted rows
with a warning instead of hiding the ratios surface. The catch now logs at debug level
with `exc_info=True`, so the warning path is not silent.

## S382-CR-005 | PASS | Locale and focused validation passed

No locale leaves were added. Focused `ruff check`, ratios integration tests, and
`python -m aeat.locales audit` passed.

## S386-CR-001 | PASS | Overview rendering is presentation-only

Reviewed the S386 scope as `vaultspec-code-reviewer`. `_overview_rendering.py` consumes
an `OverviewStatusReport` and emits localized text lines. It does not resolve
active-profile pointers, scan manifests, construct storage repositories, load settings,
read environment variables, or catch exceptions.

## S386-CR-002 | PASS | Active-profile signal is projected upstream

The renderer's only active-profile behavior is selecting the application-projected
display label for prose and falling back to the projected bucket id if the label is
missing. No storage discovery happens in the renderer.

## S386-CR-003 | PASS | Locale and focused validation passed

No locale leaves were added. Focused `ruff check`, overview rendering integration
tests, and `python -m aeat.locales audit` passed.

## S387-CR-001 | FIXED | Review queue invoice and draft adapters used ambient repository defaults

Reviewed the S387 scope as `vaultspec-code-reviewer`. `_review.py` delegates to
`project_review_queue()` and does not construct storage repositories, but
`ReviewQueue.collect()` was only partially bucket-explicit: transaction loading
received the resolved bucket id while invoice and draft loading constructed their
repositories through defaults.

`invoices_pending()` and `drafts_pending()` now require `bucket_id` for repository
loading, and `ReviewQueue.collect()` passes its bucket id to all source adapters.

## S387-CR-002 | PASS | Review CLI remains a localized application facade

The CLI layer still renders through `tr()` strings and projects `ReviewError` through
the shared CLI resolver. No raw SQL routes, storage settings, direct repository
construction, ad hoc exception classes, or new broad catch blocks were added.

## S387-CR-003 | PASS | Locale audit stayed clean for the staged review queue slice

The review queue change did not introduce locale keys. The local shared worktree
contains an untracked ledger-rule split with its own locale requirement; that repair was
performed through `python -m aeat.locales set` but remains unstaged with its owning
source split.

## S387-CR-004 | PASS | Validation passed

Focused `ruff check`, application review tests, review CLI integration tests, and
`python -m aeat.locales audit` passed.

## S388-CR-001 | PASS | Review payloads are schema-only

Reviewed the S388 scope as `vaultspec-code-reviewer`. `_review_payloads.py` declares
strict `OutputSchema` subclasses for review queue/view JSON output and registers both
envelopes with the CLI schema registry. It imports the shared `BucketId` alias from
core identity and does not open storage routes, active-profile pointers, manifests, or
remote providers.

## S388-CR-002 | PASS | Remote-provider signal is a downstream contract

The payload schema carries bucket ids, owner surfaces, next commands, and legal
reference tuples projected by the application review operator. It does not perform
provider IO, mirror persistence, redaction-sensitive rendering, or environment
wrangling.

## S388-CR-003 | PASS | Validation passed

Focused `ruff check`, payload roundtrip integration tests, and `python -m aeat.locales
audit` passed.

## S389-CR-001 | PASS | Root landing rendering is presentation-only

Reviewed the S389 scope as `vaultspec-code-reviewer`. `_root_landing.py` consumes a
`RootLandingReport` and emits localized CLI lines. It does not resolve active-profile
pointers, inspect manifests, load settings, construct storage repositories, read
environment variables, or catch exceptions.

## S389-CR-002 | PASS | Active-profile state is projected upstream

The renderer only branches on `landing.active_profile is not None` and interpolates the
already-projected profile label into localized text. The root callback and application
operator-surface builder own discovery.

## S389-CR-003 | FIXED | Root-help assertion matched stale tax-id placeholder

The installed-console refusal now guides operators with `--tax-id DNI/NIE/NIF/CIF`.
The root-help test still asserted the older `--tax-id NIF` substring, so the assertion
now matches the current localized guidance.

## S389-CR-004 | PASS | Validation passed

Focused `ruff check`, root-help/operator-surface integration tests, and `python -m
aeat.locales audit` passed.

## S390-CR-001 | PASS | CLI schema module is a re-export boundary

Reviewed the S390 scope as `vaultspec-code-reviewer`. `_schemas.py` imports and
re-exports the canonical schema registry, output base classes, envelope type, and JSON
emit helpers from `aeat.core.json_contract`. It does not create storage repositories,
read active-profile pointers, inspect manifests, load settings, access environment
variables, perform remote IO, or catch exceptions.

## S390-CR-002 | FIXED | Config payload schemas were not loaded before the exact registry gate

The JSON schema conformance test documented that payload modules must be imported before
the gate compares CLI leaves to `SCHEMA_REGISTRY`, but config payloads were missing from
that import setup. The gate now imports `_config_payloads`; the assertion remains an
exact registry-to-leaf match with no allowlist.

## S390-CR-003 | PASS | IVA wallet seed errors have centralized base and registry

Validation surfaced existing Modelo IVA wallet seed errors whose base still derived from
bare `Exception` earlier in the shared-worktree run and lacked central `ErrorCode`
declarations. Current HEAD now has the seed base deriving from `ModeloError`, and the
declarations live in the core registry.

## S390-CR-004 | TRACKED | Cross-period clean-state locale repair belongs to its source slice

The shared dirty worktree also contains a cross-period clean-state implementation with a
new localized refusal key. The locale leaf was created locally through `python -m
aeat.locales`, but it is not staged in S390 because the owning source class is not
present in committed HEAD. It remains tracked with the cross-period slice.

## S390-CR-005 | FIXED | Config repair extraction kept schema gate and locale keys aligned

The config repair callback moved to `_config/_repair_cli.py`, so the zero-bare-emit gate
now consumes the documented exemption path set instead of hard-coding only
`_config/__init__.py`. The extracted repair integrity commands also gained nested
localized help strings through `python -m aeat.locales`.

## S390-CR-006 | PASS | Validation passed

Focused `ruff check`, CLI schema conformance integration tests, error-registry
enforcement tests, and `python -m aeat.locales audit` passed in the current shared
worktree.

## S391-CR-001 | PASS | TTY helpers have no storage authority

Reviewed the S391 scope as `vaultspec-code-reviewer`. `_tty.py` checks terminal state
through `sys.stdin`, `sys.stdout`, and `sys.stderr`, and returns rendering/refusal
decisions. It does not resolve active profiles, inspect manifests, open repositories,
persist data, read raw environment variables, or call remote providers.

## S391-CR-002 | PASS | Environment flags are centralized through settings

Colour resolution uses the active CLI flag context plus `Settings.no_color` and
`Settings.aeat_force_color`. The module does not duplicate `NO_COLOR` or
`AEAT_FORCE_COLOR` parsing.

## S391-CR-003 | PASS | Non-TTY refusal is registry-backed

`NonTtyRefusedError` derives from `AeatError`, keeps positional args empty so locale
resolution uses the registry message key, and is declared in the centralized application
error registry.

## S391-CR-004 | FIXED | Direct profile wizard callbacks bypassed error rendering

Profile lifecycle validation showed direct `profile_app` invocations of generated
profile `create`/`edit` callbacks bypassed the root app's error boundary. The generated
callbacks are now registered through `command_error_boundary`, so non-TTY refusals render
typed recovery guidance in direct sub-app tests and root CLI usage.

## S391-CR-005 | FIXED | Deprecated tax-id placeholder removed from profile lifecycle assertion

The profile-create recovery assertion expected the old `--tax-id NIF` placeholder. It
now asserts the current `--tax-id DNI/NIE/NIF/CIF` operator guidance.

## S391-CR-006 | PASS | Validation passed

Focused `ruff check`, TTY locale integration tests, profile lifecycle integration tests,
error-registry tests, JSON schema conformance tests, and `python -m aeat.locales audit`
passed.

## S392-CR-001 | PASS | Registry CLI read paths stay read-only

Reviewed the S392 scope as `vaultspec-code-reviewer`. `registry.py` delegates to
application registry verification services and resolves default registry/source read
roots through `bundled_path()`. The `verify-filed-state` command is correctly treated
as a runtime-default surface because it loads filed-state observations through the
encrypted observation store rather than direct filesystem-only paths.

## S392-CR-002 | PASS | Operator path inputs stay explicit

The registry, source, workbook, scenario, tape, and output paths are explicit Typer
`Path` options. Defaults point at bundled resources or centralized settings; there is
no fallback to ambient profile roots for operator-provided export paths.

## S392-CR-003 | PASS | Output contract is schema-backed

All command result paths use `_emit_envelope()` with registered registry payload models.
The JSON schema conformance gate passed for the current CLI tree.

## S392-CR-004 | PASS | Validation passed

Focused `ruff check`, registry CLI integration tests, schema conformance tests, and
`python -m aeat.locales audit` passed.

## S392-CR-005 | PASS | Settings centralization repaired parity tape default

Second-pass review found the `registry parity run` default tape archive root hardcoded
as `var/aeat/parity`. The repair adds `Settings.aeat_registry_parity_store_dir`,
documents `AEAT_REGISTRY_PARITY_STORE_DIR`, resolves omitted `--store-root` values via
`load_settings()`, and preserves explicit operator paths. The focused parity settings
resolver test and `.env.example`/`Settings` alignment tests passed.

## S442-CR-001 | PASS | Modelo projection stays a delegated manifest-discovery surface

Reviewed `src/aeat/application/modelo/_projection.py` as the S442 scope. The module
does not construct secure-object repositories, inspect bucket manifests, open SQL
routes, read environment variables, or persist files directly. It delegates active
profile-derived inputs to `resolve_profile_sourced_bindings()` and existing modelo
actions, so the `manifest-discovery` disposition is appropriate for this split-module
closeout.

## S442-CR-002 | PASS | Exception, locale, and validation gates passed

Projection and comparison exceptions derive from `AeatError` and are enrolled in the
central application error registry. Focused ruff, modelo projection integration tests,
modelo CLI spine selection, error-registry tests, and `python -m aeat.locales audit`
passed.
