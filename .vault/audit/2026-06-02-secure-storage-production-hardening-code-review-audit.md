---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-02'
modified: '2026-06-02'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# `secure-storage-production-hardening` Code Review

## S49-001 | PASS | Final SecureStorage W06.P11 review found no findings

Reviewer `Beauvoir` completed the final `W06.P11.S49` SecureStorage review across the `S45` through `S48` commit set, step records, audit records, and scoped implementation/test files.

No findings were reported. The review verified that runtime-bound repositories fail closed for missing, stale, expired, or unsecured active sessions; locale-backed error keys are present; exceptions derive from AEAT storage/core bases; and the new tests avoid fakes, mocks, stubs, monkeypatches, skips, xfails, naked environment mutation, and mirrored business logic.

Closure assessment: `W06.P11.S49` can close based on the reviewed evidence. Live Google Drive mirror and formula-level calc-sheets proof is tracked separately by `W06.P11.S428` through `W06.P11.S431`, with 2026-06-03 continuation evidence under `W06.P11.S441`.

## S431-002 | MEDIUM | RESOLVED | Google Sheets quota failures were generic network errors with no client retry

Live connector reads on 2026-06-02 hit Google Sheets HTTP 429 `ReadRequestsPerMinutePerProject`, but the shared Google API executor called `request.execute()` with no retry count and mapped unmapped HTTP failures to `OutboundStorageNetworkError`. That made quota pressure operationally indistinct from generic transport failure and left the S431 quota-aware claim under-supported.

Resolution: `execute_request` now calls google-api-python-client requests with `num_retries=3` and maps HTTP 429 plus rate-limit HTTP 403 payloads to the existing `OutboundStorageQuotaError`. Focused tests use real `httplib2.Response` plus `googleapiclient.errors.HttpError`, and no fake response / skip path remains in `test_api.py`.

## S43-005 | MEDIUM | RESOLVED | One-hop mirror lineage could not prove multi-revision stale ancestry

The mirror comparator could not prove that a remote root revision more than one local revision behind was an ancestor, so the implementation either had to classify true stale mirrors as conflicts or rely on timestamp-only inference. That left S43's stale-vs-conflict classification incomplete.

Resolution: S440 persists `revision_ancestor_ids` on secure-object rows, exposes the tuple in `SecureObjectRawRow`, includes it in `RemoteMirrorObjectManifest`, and classifies stale mirrors by revision-id ancestry. Real repository tests now prove both the three-save stale case and the unrelated older-root conflict case.

## S441-009 | PASS | Live Drive and Sheets continuation proof verified

The `W06.P11.S441` review found no HIGH or CRITICAL issues. The evidence is live and bounded: active profile status and read-only probe passed, the Google Drive connector read the configured app-owned hierarchy, `_probe` was empty after the enabled live provider test, the live workbook exported as XLSX, formula reads returned the Modelo 130 chain, value reads first hit real Google Sheets HTTP 429 and then succeeded after quota reset, and focused pytest/Ruff gates passed.

The current tree contains the IVA wallet calculation docstring argument-description repair needed for the targeted Ruff gate; the impacted IVA wallet test passed with 19 tests and the broader calc-sheets/export batch passed with 49 tests.

## S425-006 | PASS | Business-operation invoice JSONL store migrated to secure objects

Reviewer `Nash` completed the `W17.P37.S425` review across the business-operation invoice service, namespace registry, namespace coverage tests, and sensitive persistence allowlist change.

No findings were reported. The review verified that payable and collectible business-operation invoice persistence routes through `BusinessOperationInvoiceRepository` and `secure_object_repository_for_bucket`, object keys are bucket/source-kind scoped as `{bucket_id}:{source_kind}`, production JSONL read/write logic is removed, tests use real runtime secure-object behavior without fakes or monkeypatching, and reviewed files do not use naked environment access.

Closure assessment: `W17.P37.S425` can close based on the reviewed evidence. The separate `_iva_compensation_wallet.py` diagnostic write inventory delta remains outside this S425 slice.

## S97-007 | PASS | Application side-store migration closeout verified

Reviewer `Nietzsche` completed the `W12.P24.S97` review across the S96 side-store classification, W17 ledger migration evidence, and current application side-store modules.

The review reported one LOW stale-documentation issue in purchase invoice evidence method docstrings that still referenced JSONL. That wording was corrected to describe the encrypted bucket-local secure-object catalogue.

Closure assessment: `W12.P24.S97` can close. The scoped modules no longer contain default JSON or JSONL sensitive side-store read/write paths, and the retained evidence ZIP export remains an explicit operator-directed output boundary.

## S99-008 | PASS | Retained evidence ZIP export does not become sensitive persistence

Reviewer `Averroes` completed the `W12.P24.S99` review for the retained evidence export proof.

No findings were reported. The review verified the new test uses real `EvidenceBundleService`, a real isolated runtime profile, and raw secure-object repository iteration to prove the ZIP is written to a caller-supplied path outside the storage root while the encrypted secure-object catalogue fingerprint remains unchanged.

Closure assessment: `W12.P24.S99` can close. The unrelated `_iva_compensation_wallet.py` diagnostic write inventory delta remains outside this S99 slice.

## S100-009 | PASS | Scanner delta closeout artifacts are honest and scoped

The S100 review covered `2026-06-02-secure-storage-production-hardening-W12-P25-S100-scanner-delta.md` and the matching step record. Reviewer agent `Fermat` was spawned with the `vaultspec-code-reviewer` role but hit the account usage limit before returning findings, so the host review is recorded in `2026-06-03-secure-storage-production-hardening-W12-P25-S100-review.md` with that limitation preserved.

No high or critical findings were identified. The audit records baseline/current production and test signal deltas, discloses that the original scanner source was not present as a standalone script, and leaves residual plain-file, route/session, direct-constructor, manifest-discovery, bootstrap-custody, side-store, and remote-mirror risks owned by S101, S102, and W12.P26 rather than overclaiming rollout completion.

During validation, the hardening guard exposed one new unapproved explicit database-route setup in `src/aeat/application/live/test_iva_wallet_capture_backend.py`. The test was migrated to real runtime-profile storage and runtime-bound repository injection rather than added to the explicit-route allowlist.

## S101-010 | PASS | Focused active-profile runtime migration gates verified

The `W12.P25.S101` review found no HIGH or CRITICAL issues and no open residuals.

The evidence is real validation rather than assumed coverage: storage/runtime passed 73 tests, profile lifecycle passed 30 tests, CLI lifecycle/workflow passed 76 tests after splitting the timed-out combined command, workflow persistence/resume/profile-health passed 36 tests, domain/application repositories passed 134 tests after replacing a stale removed test path, outbound storage/Google adapter tests passed 47 tests, the `SecureBoundRepository` contract passed 3 tests, and targeted Ruff passed over the focused surfaces.

Resolved process issues are tracked in the S101 review: the timed-out combined CLI run is not counted as evidence, and the stale `src/aeat/domain/filing/test_repository.py` path was replaced with current repository and secure-storage roundtrip files before closure.

## S203-012 | PASS | Diagnostics runtime degradation follow-up verified

The final `W12.P26.S203` follow-up review found no new defects in the scoped diagnostics test and tracking diff after the prior reviewer findings were addressed.

The review verified that diagnostics secure-object aggregate degradation is covered for missing active bucket sessions and active-session route mismatches, both cases assert debug logging with route-specific failure detail, and the migrated-runtime gate now carries explicit diagnostics degradation coverage beside the raises-only refusal matrix. The plan ledger is aligned with recorded `AFR-101`, `AFR-102`, and `AFR-103` closures, and the generated `LINK RULES` block is removed from the plan diff.

Closure assessment: `W12.P26.S203` remains closed. No production code changed in this follow-up, and the test additions do not introduce fakes, mocks, monkeypatches, skips, xfails, tautological assertions, naked environment access, or mirrored business logic.

## S102-011 | HIGH | OPEN | Final runtime rollout disposition proof still has unchecked W12.P26 rows

The `W12.P25.S102` review cannot close. After the S119-S136 continuation, the plan still has 217 unchecked W12.P26 affected-file closeout rows, and the affected-file register still has 220 rows marked `pending`.

This is the exact surface S102 must prove: 48 `runtime-default`, 75 `manifest-discovery`, 13 `bootstrap-custody`, 36 `plaintext-exception`, 44 `remote-mirror`, and 1 `retired` row remain unchecked. Three checked locale rows also still have pending AFR status and no local S393-S395 evidence artifact.

Action remains in scope: execute the W12.P26 affected-file ledger and either restore/write the S393-S395 evidence or reopen those rows. Do not mark S102 complete until the ledger supports the final disposition claim.

## S121-012 | PASS | Export record-spec primitive has no storage backend behavior

The `W12.P26.S121` review closed `AFR-019` for `_record_spec.py`. The file is a fixed-width Fichero BOE schema and encoder primitive, not a remote provider or storage backend.

Focused validation passed with 101 primitive export-format tests and targeted Ruff. A source scan for secure-storage, settings-route, filesystem, and provider APIs returned no matches in `_record_spec.py`.

## S122-013 | PASS | G313 censo live adapter is outbound-only

The `W12.P26.S122` review closed `AFR-020` for `_censo_live.py`. The file is an authenticated AEAT Sede browser-fetch adapter that returns parsed censo facts; it does not select a storage provider, construct secure-object repositories, route SQL storage, or write local files.

Focused censo live and Playwright wait-constant tests passed with 6 tests, targeted Ruff passed, and the storage/settings/filesystem/provider API source scan returned no matches.

## S123-014 | PASS | Declarations reader storage signals are bounded remote-mirror concerns

The `W12.P26.S123` review closed `AFR-021` for `_declarations.py`. The file is an authenticated AEAT Sede filed-declaration reader: it opens the declarations register, applies remote read guards, captures AEAT-served artefacts, and returns normalized observations. It does not select an outbound storage provider, construct secure-object repositories, route SQL storage, or create durable plaintext side stores.

The active-profile signal is limited to browser-session profile binding through the active bucket id. Runtime knobs use `Settings` or `load_settings()`, and the reviewed file has no naked environment reads. The plain-file signals are bounded to Playwright temporary download reads and a declaration-PDF parser scratch path. The continuation review found the original `NamedTemporaryFile(delete=False)` bridge too weak for taxpayer PDF bytes and replaced it with a private `mkstemp` fd helper plus focused unlink coverage.

Focused declaration-PDF observation and read-guard tests passed with 12 tests, targeted Ruff passed, and source scans found no durable storage backend/provider behavior in the reviewed module.

## S120-015 | MEDIUM | RESOLVED | Broader export validation blockers were real, not external noise

The initial S120 closeout under-reported the broader export-format run as blocked by unrelated registry validation. Continuation validation pursued the failure chain instead: Modelo 151 now passes its focused registry test, invalid Modelo 714 placeholder formulas were removed rather than accepted as fake coverage, and the Modelo 303 golden SHA was refreshed only after adding official DP30303 offset assertions for casillas 110, 78, and 87.

Evidence: Modelo 151 registry passed 4 tests, Modelo 714 registry passed 4 tests, the Modelo 303 golden test passed, targeted Ruff passed, and the broader export-format batch passed with 114 tests.

## S123-016 | MEDIUM | RESOLVED | Declaration PDF bbox temp bridge used weaker plaintext custody

`_declarations.py` previously wrote sensitive declaration PDF bytes through `NamedTemporaryFile(delete=False)` before reopening the path for pdfplumber. The file was short-lived, but it was still plaintext-at-rest with weaker custody than the existing sensitive temp convention.

Resolution: `_temporary_sensitive_pdf_path()` now creates the path with `mkstemp`, writes through the already-open private fd, closes it before parsing, and unlinks on exit. A real filesystem test proves payload visibility during the context, private mode on POSIX, and removal after exit. The broader Sede batch passed with 155 tests.

## W12P26-017 | MEDIUM | RESOLVED | Production write inventory had unreviewed diagnostic/reference writers

The production write inventory failed during S123 validation on the IVA wallet diagnostic summary and ECB reference-rate refresh writes. The fix classified both instead of ignoring the gate: the wallet diagnostic has a real Playwright-backed redaction test proving raw query/input values, wallet amounts, and table labels do not enter the summary, while ECB refresh writes are documented as non-user official reference-data maintenance after parser validation.

Evidence: the full production sensitive persistence policy passed with 2 tests, and targeted Ruff passed.

## S121-S128-018 | PASS | AEAT export/Sede/verify affected-file slice closed

`W12.P26.S121` through `W12.P26.S128` are now checked, and `AFR-019` through `AFR-026` are marked `closed` in the affected-file register. No HIGH or CRITICAL findings remain for this slice; the medium findings above were resolved with code/test changes and current validation.

## S129-019 | PASS | Calc-sheets apply remains a one-way remote mirror

The `W12.P26.S129` review closed `AFR-027` for `_calc_sheets_apply.py`. The adapter materialises a pure `SheetExportPlan` into app-owned Google Drive folders and a Google Sheets workbook, then returns a typed result. It does not select local storage, construct secure-object repositories, route SQL storage, write local files, or consume Google Sheets edits into local state.

The reviewed settings signal uses `Settings` for the Drive vault folder name rather than naked environment access. Focused calc-sheets apply/pull tests passed with 19 tests, targeted Ruff passed, and the source scan found no DB route, naked environment, secure-object constructor, local storage constructor, or local file read/write matches.

## S130-020 | PASS | Calc-sheets pull refuses unowned or stale readback

The `W12.P26.S130` review closed `AFR-028` for `_calc_sheets_pull.py`. The adapter reads remote Google Sheets values into typed pull records, but it does not mutate local state or write local persistence. Drive ownership and registry metadata gates prevent arbitrary or stale workbooks from flowing into local compute.

Focused pull/apply tests passed with 38 tests, including stale and missing metadata refusal coverage. Targeted Ruff passed, and the source scan found no DB route, naked environment, secure-object constructor, local storage constructor, or local file read/write matches.

## S131-021 | PASS | Google OAuth errors are typed exceptions only

The `W12.P26.S131` review closed `AFR-029` for `_errors.py`. The active-profile signal came from error descriptions for missing profile binding, not profile or manifest implementation. The module only declares Google OAuth exception classes rooted at `AeatError`.

Registry enforcement, Google package allowlist, Google records, and CLI Google localisation tests passed with 28 total tests across the focused commands. Targeted Ruff passed. No source edits were required.

## S132-022 | PASS | OAuth flow defers persistence to secure session-store boundary

The `W12.P26.S132` review closed `AFR-030` for `_oauth_flow.py`. The flow resolves active profile/tax-id state for unsecured-mode refusal, runs the Google loopback OAuth flow, and returns strict OAuth records; it does not persist records or construct storage backends itself.

Focused Google records, package allowlist, and CLI Google localisation tests passed with 24 tests, targeted Ruff passed, and the source scan found no DB route, naked environment, secure-object constructor, local storage constructor, or local file read/write matches. Live OAuth consent remains opt-in evidence outside this offline ledger closure.

## S129-023 | MEDIUM | RESOLVED | Calc-sheets re-export accumulated duplicate remote workbook structure

Manual live inspection of the configured app-owned `AEAT 130 1T 2025` workbook found duplicate `aeat_*` developer metadata and duplicate app protected ranges after repeated exports. The apply adapter now deletes only adapter-managed developer metadata and protected ranges before recreating them, and the pull adapter refuses conflicting duplicate identity metadata with a typed, locale-backed `OutboundStorageConflictError`. The focused Google adapter suite passed with 131 tests, targeted Ruff passed, the locale audit passed through `python -m aeat.locales`, and the live pull/compute command still succeeds against the existing workbook.

## S132-024 | MEDIUM | RESOLVED | OAuth local-server fallthrough leaked raw upstream exceptions

The OAuth flow's local-server wrapper could re-raise unclassified `InstalledAppFlow.run_local_server()` exceptions outside the `GoogleAuthError` hierarchy caught by the CLI. `_raise_local_server_error()` now wraps the fallthrough as `GoogleAuthNetworkError` with the original exception preserved as cause; focused OAuth tests cover browser, network, and unclassified failure translation.

## S133-025 | MEDIUM | RESOLVED | Localized profile-binding suggestion evidence overclaimed locale parity

Rerunning `python -m aeat.locales audit` disproved the S133 artifact claim: the `adapters.google.profile_binding.suggestions.create_profile` key was missing from all four locale catalogues. The missing leaves were added to `en.yml`, `es.yml`, `ca.yml`, and `hu.yml`; the locale audit now passes.

## S134-S136-026 | PASS | Google records, stale refresh row, and session store are closed

`W12.P26.S134` through `W12.P26.S136` are now checked. `AFR-032` is closed as `remote-mirror`, `AFR-033` is closed as `retired` because `_refresh.py` is absent from disk and `git ls-files`, and `AFR-034` is closed as `runtime-default` through `secure_object_repository_for_active_bucket()`.

## S132-027 | HIGH | RESOLVED | OAuth unsecured-mode preflight treated missing profile state as no tax id

The code-reviewer found that `_oauth_flow.resolve_active_tax_id()` degraded a missing active-profile bucket manifest or missing profile aggregate to `""`. Because `check_unsecured_mode_safety()` only refuses a non-empty real tax id, a stale active-profile pointer under `unsecured` could proceed toward loopback OAuth instead of failing closed before network IO.

Resolution: missing bucket manifests and missing profile records now raise `GoogleAuthProfileUnboundError` with `translated_message="adapters.google.oauth_flow.errors.profile_state_unresolved"` and `tr()`-resolved repair guidance. `test_oauth_flow.py` covers both a missing manifest and a real isolated active-bucket runtime whose profile aggregate is absent, proving the login flow refuses before OAuth network IO.

## S130-028 | MEDIUM | RESOLVED | Pull adapter retained unlocalized operator-facing refusals

The code-reviewer found that `_calc_sheets_pull.py` still had public pull/compute refusal paths without translated-message keys or localized remediation: blank spreadsheet id, foreign Drive ownership, and metadata/snapshot compute mismatch.

Resolution: all three paths now pass `translated_message`; the ownership and compute remediations use `tr()` suggestions. `test_pull_adapter_helpers.py` covers blank-id validation before service construction, and `test_compute_from_pull.py` covers the stale-workbook refusal message/suggestion. The foreign-ownership path is source-reviewed because exercising it without a fake Google Drive service would violate the real-behavior test rule.

## S129-S130-029 | PASS | New export parity ADRs constrain this bundle's claims

The 2026-06-03 modelo export evidence/workbook parity ADRs were read before closure. This bundle only hardens the Google Sheets transport mirror: idempotent app-managed metadata/range cleanup, duplicate metadata conflict refusal, localized pull/compute refusals, and OAuth preflight failure boundaries. It does not claim the new `Evidencia` surface, bundled ledger evidence, offline/online single-builder parity, explicit start/final anchors, official-layout parity gates, documentary parity tier migration, or BOE golden-SHA sibling conformance work.

## S206-030 | PASS | Generic tabular export plaintext exception verified

The `W12.P26.S206` review found no HIGH or CRITICAL issues and no remaining
open findings in the scoped diff.

The review verified that `serialize_tabular_rows()` remains pure in-memory
serialization with no path read/write, settings, environment, active-profile,
SQL, or secure-object repository access. The remaining digest validation path no
longer raises a naked `ValueError`; malformed digests carry `ExportFieldError`
in pydantic `ctx.error` with the registered refused-export-field locale key.
The XLSX branch is now covered by real openpyxl readback of generated bytes.

Closure assessment: `W12.P26.S206` can close as `plaintext-exception`. The
2026-06-03 modelo export ADRs were considered, and this row does not claim
modelo workbook parity, evidence bundling, visual styling, official-layout
parity, or BOE fichero byte-shape coverage.

## S207-031 | PASS | Filing package init manifest-discovery closeout verified

The `W12.P26.S207` review found no storage-routing defect in
`src/aeat/application/filing/__init__.py`.

The source scan found no direct file read/write, storage-path helper, settings
load, naked environment read, SQL route, secure-object repository construction,
or runtime repository factory call in the reviewed file. The manifest-bucket
signal is registry/resource discovery through the bundled model authority and
registry snapshot references. Re-exported filing operations do not execute
persistence or export writes at import time and remain owned by their specific
affected-file rows.

Closure assessment: `W12.P26.S207` can close as `manifest-discovery`. The
review also logged broader raw filing builder/calculation message debt for the
plan's W16 observation pool; that convention issue is tracked, not resolved by
this storage-disposition row.

## S208-032 | PASS | Filing history runtime repository closeout verified

The `W12.P26.S208` review found no findings in the filing history repository
runtime-default slice.

The implementation resolves default storage through the application filing
runtime helper and `SecureBoundRepository`, uses the centralized
`APPLICATION_FILING_HISTORY_NAMESPACE`, and persists AUDIT-sensitivity history
records through encrypted secure objects. Focused tests passed for encrypted
payload evidence, classification refusal, missing active session refusal,
route-session mismatch refusal, and active-profile isolation.

Closure assessment: `W12.P26.S208` can close as `runtime-default`; no production
code change was required.

## S209-033 | PASS | Filing review runtime repository closeout verified

The `W12.P26.S209` review found no remaining findings in the filing review
runtime-default slice.

The default approval-basis path loads transaction state through
`TransactionCatalogueRepository` and the active bucket storage runtime rather
than constructing raw secure-object storage or reading plaintext side files.
The stale in-process catalogue-cache risk is removed, and focused real-behavior
tests prove unready runtime refusal plus fresh persisted transaction-catalogue
changes surfacing as `TRANSACTION_CATALOGUE_CHANGED`.

Review-facing approval errors and stale-reason descriptions are now
locale-backed. Locale coverage was verified with the required
`python -m aeat.locales audit` invocation.

Closure assessment: `W12.P26.S209` can close as `runtime-default`.

## S210-034 | PASS | Filing runtime repository helper closeout verified

The `W12.P26.S210` review found no remaining findings in the filing runtime
repository helper slice.

The helper resolves explicit bucket ids after trimming, falls back to
`resolve_active_bucket_id()` for active-profile authority, and delegates
secure-object construction to `secure_object_repository_for_bucket()`. It does
not read environment variables directly, construct raw production storage, or
derive SQL routes itself.

Focused tests now cover explicit id handling, blank id refusal, active-profile
fallback, no-active-profile refusal, and unready runtime refusal. The migrated
runtime matrix remains the scoped consumer gate for the filing-history path
using this helper.

Closure assessment: `W12.P26.S210` can close as `runtime-default`.

## S211-035 | PASS | Filing testing registry helper closeout verified

The `W12.P26.S211` review found no storage-routing defect in the
registry-backed filing test helper.

The helper resolves bundled registry snapshot metadata through the runtime
schema provider and uses an explicit empty `TransactionCatalogue` when it calls
`approve_draft()`. It does not construct storage repositories, route SQL, read
or write files, inspect active sessions, or read settings/environment state
directly.

Closure assessment: `W12.P26.S211` can close as `manifest-discovery`.

## S212-036 | PASS | Filing runtime provider closeout verified

The `W12.P26.S212` review found no storage-routing defect in the filing runtime
schema/profile provider.

The module uses bundled registry/source roots for validated registry manifest
discovery and tree fingerprinting, then projects snapshots into filing schema
views. Active profile loading is delegated to workflow/wizard repository
surfaces. The reviewed file does not construct secure-object repositories,
route SQL, inspect active sessions, or read settings/environment state directly.
Filing-runtime `ModeloBuilderError` boundaries now carry locale metadata and
non-sensitive context payloads for the reviewed missing-registry/profile/modelo
selection/revision/provider/year-period/casilla-type failures.

Closure assessment: `W12.P26.S212` can close as `manifest-discovery`.

## S213-037 | PASS | Inventory service runtime-default closeout verified

The `W12.P26.S213` review found that the inventory application service is
runtime-backed secure storage rather than manifest-only discovery.
`InventoryService` resolves inventory ledgers through
`secure_object_repository_for_bucket()` and `InventoryLedgerRepository`, and it
emits mutating audit events through `BucketEventHistoryRepository`.

The plan target for `AFR-111` is corrected to `runtime-default`, matching the
W12 side-store classification that records inventory ledgers as secure-object
migration completed. The service uses settings-backed runtime resolution,
typed AEAT exception boundaries with locale metadata, and real-runtime tests
for bucket isolation, route mismatch refusal, encrypted persistence, and
legacy JSON side-store absence.

Closure assessment: `W12.P26.S213` can close as `runtime-default`.

## S214-038 | PASS | Invoice importing plaintext exception closeout verified

The `W12.P26.S214` review found that invoice importing reads only the
operator-supplied CSV/JSON import source as plaintext. Non-dry-run durable
invoice catalogue state goes through `InvoiceCatalogueRepository`, which
persists FINANCIAL secure-object payloads through the active bucket runtime.

Malformed JSON, invalid JSON shape, invalid flat `base_total`, invalid invoice
kind, and import file read failures now raise localized `InvoiceValidationError`
instances. The file-read failure path records debug evidence with file name and
error type before chaining the original `OSError`.

Closure assessment: `W12.P26.S214` can close as `plaintext-exception`.

## S215-039 | PASS | Invoice linking runtime-default closeout verified

The `W12.P26.S215` review found that invoice-to-transaction linking writes
through runtime-bound invoice and transaction catalogue repositories, not a
manifest-only discovery path. The plan target for `AFR-113` is corrected to
`runtime-default`.

The service now passes the requested `bucket_id` into the default invoice
repository, matching the transaction repository binding. Missing transaction
and post-link missing invoice refusals use localized `InvoiceLinkError`
metadata, and the linking locale leaves were set through `python -m
aeat.locales`.

Closure assessment: `W12.P26.S215` can close as `runtime-default`.

## S216-040 | PASS | Invoice query runtime-default closeout verified

The `W12.P26.S216` review found that invoice query projections read durable
invoice and transaction catalogue state through runtime-backed repositories.
The plan target for `AFR-114` is corrected to `runtime-default`.

`verify_invoice_repository_links(bucket_id=...)` now passes the requested
bucket to `InvoiceCatalogueRepository`, matching the transaction repository
binding. The new real-runtime test persists linked catalogues and verifies the
repository-backed consistency query against the requested bucket.

Closure assessment: `W12.P26.S216` can close as `runtime-default`.

## S217-041 | PASS | Invoice reconciliation runtime-default closeout verified

The `W12.P26.S217` review found that invoice reconciliation reads and writes
durable invoice and transaction catalogue state through runtime-backed
repositories. The plan target for `AFR-115` is corrected to `runtime-default`.

`reconcile_invoice_repositories(bucket_id=...)` now passes the requested bucket
to `InvoiceCatalogueRepository`, matching the transaction repository binding.
The new real-runtime test persists both catalogues, applies reconciliation, and
verifies both persisted catalogues update under the requested bucket.

Closure assessment: `W12.P26.S217` can close as `runtime-default`.

## S228-042 | PASS | Live expedientes remote-mirror closeout verified

The `W12.P26.S228` review found that live expedientes captures are encrypted
remote mirrors of the authenticated AEAT declaration-register read surface.
The service persists through `SecureSnapshotRepository` and
`secure_object_repository_for_bucket()`, not plaintext JSONL files or direct SQL
routes.

Expedientes object-key validation and lookup refusals now carry locale-backed
metadata. The not-found and ambiguous-prefix paths avoid leaking bucket ids or
matched full snapshot ids while retaining bounded diagnostic context.

Closure assessment: `W12.P26.S228` can close as `remote-mirror`.

## S229-043 | PASS | Live notifications remote-mirror closeout verified

The `W12.P26.S229` review found that live notification snapshots are encrypted
remote mirrors of the authenticated AEAT notifications read surface. The
affected-file row is corrected from stale `manifest-discovery` plaintext
metadata to `remote-mirror` with secure-object and remote-provider signals.

The service persists through `SecureSnapshotRepository`,
`LIVE_NOTIFICATIONS_SNAPSHOT_NAMESPACE`, and
`secure_object_repository_for_bucket()`. Refusal paths now carry locale-backed
metadata and avoid leaking bucket ids or matched full snapshot ids.

Closure assessment: `W12.P26.S229` can close as `remote-mirror`.

## S230-044 | PASS | Shared live snapshot base runtime-default closeout verified

The `W12.P26.S230` review found that `SecureSnapshotRepository` remains the
shared runtime-backed secure-object repository for live snapshot services. It
uses registered namespace definitions and runtime-created secure-object
repositories rather than plaintext JSONL stores or direct SQL routes.

The list-time bucket-contamination residual from the earlier S39 review is now
resolved: `list_snapshots()` raises a localized `LiveApplicationInputError`
when a decrypted payload bucket differs from the repository bucket. A
real-repository test seeds the contaminated row through the registered test
namespace and verifies fail-closed behavior.

Closure assessment: `W12.P26.S230` can close as `runtime-default`.

## S231-045 | PASS | Live verify remote-mirror closeout verified

The `W12.P26.S231` review found that live verify observations are encrypted
audit mirrors of authenticated AEAT verify checks. The affected-file row is
corrected from stale `manifest-discovery` plaintext metadata to
`remote-mirror` with secure-object and remote-provider signals.

The service persists through `VerifyObservationRepository`,
`LIVE_VERIFY_OBSERVATION_NAMESPACE`, and `secure_object_repository_for_bucket()`.
Refusal paths now carry locale-backed metadata, avoid leaking bucket ids or
matched full observation ids, and fail closed when list-time decrypted payload
buckets do not match the repository bucket.

Closure assessment: `W12.P26.S231` can close as `remote-mirror`.

## S232-046 | PASS | Modelo package API manifest-discovery closeout verified

The `W12.P26.S232` review found that `src/aeat/application/modelo/__init__.py`
is a package API facade only. It imports and re-exports modelo application
services and errors, documents explicit `bucket_id` application boundaries, and
does not construct repositories, load settings, inspect environment variables,
open files, swallow exceptions, or mutate storage.

The 2026-06-03 modelo export evidence/workbook parity ADRs were reviewed. Their
constraints apply to downstream export builders and parity gates, not this
package re-export surface.

Closure assessment: `W12.P26.S232` can close as `manifest-discovery`.

## S233-047 | PASS | Modelo actions remote-mirror closeout verified

The `W12.P26.S233` review found that `src/aeat/application/modelo/_actions.py`
is a modelo lifecycle orchestration layer over runtime-backed secure-object
repositories and live workflow/provider gates. Local durable state is delegated
to domain repositories and workflow persistence; the action module does not own
plaintext side stores or direct SQL secure-object routing.

Vaultspec RAG semantic searches were used for duplication review. The Modelo
303 IVA wallet prior-compensation gate clusters in `_iva_wallet_gate.py`, while
modelo secure-object persistence clusters in domain runtime repositories. The
remaining `_actions.py` compatibility alias points at the extracted gate helper
and does not duplicate business logic.

Closure assessment: `W12.P26.S233` can close as `remote-mirror`.

## S234-048 | PASS | Modelo binding-readiness manifest-discovery closeout verified

The `W12.P26.S234` review found that `src/aeat/application/modelo/_binding_readiness.py`
is a query helper for the `bindings list --missing` surface. It resolves the
registry scope and delegates profile fact projection to `_profile_binding.py`;
it does not construct storage repositories, select secure storage backends,
write plaintext side stores, inspect environment variables, or own durable
object state.

Vaultspec RAG semantic searches were used for duplication review. The binding
readiness query clusters in `_binding_readiness.py`, profile projection clusters
in `_profile_binding.py`, and the CLI caller remains a presentation/filter
surface. Conservative registry/profile fallback branches now log debug
diagnostics before returning the empty resolved-binding set.

Closure assessment: `W12.P26.S234` can close as `manifest-discovery`.

## S235-049 | PASS | Modelo borrador binding manifest-discovery closeout verified

The `W12.P26.S235` review found that `src/aeat/application/modelo/_borrador_binding.py`
is an application binding resolver and source-mesh adapter for explicitly
selected Modelo 100 borrador snapshots. Durable snapshot persistence remains
owned by the live borrador repository and runtime secure-object backend; this
module validates eligibility, axis, lifecycle, and precedence before returning
typed binding values.

Vaultspec RAG semantic searches were used for duplication review. Borrador
binding ownership clusters in `_borrador_binding.py`, profile binding ownership
clusters in `_profile_binding.py`, and calculation orchestration calls into both
from `_actions.py`. User-facing borrador binding refusals now carry locale keys
and structured context, and bucket-mismatch errors no longer echo bucket ids.

Closure assessment: `W12.P26.S235` can close as `manifest-discovery`.

## S236-050 | PASS | Modelo fichero-BOE export plaintext-exception closeout verified

The `W12.P26.S236` review found that `src/aeat/application/modelo/_export.py`
intentionally writes an operator-selected local fichero-BOE artefact and appends
a `MODELO_EXPORTED` bucket event through the repository boundary. The affected
file row was corrected from stale `manifest-discovery` to `plaintext-exception`
with an explicit `plain-file` signal.

The accepted 2026-06-03 export evidence, workbook parity, and visual-design ADRs
were reviewed before closure. This step hardens the fichero-BOE export boundary
and refusal paths; it does not claim the shared workbook builder, Evidencia tab,
offline/online workbook materialiser parity, visual facets, or official-layout
parity gate. User-facing export refusals now carry locale keys and structured
context, and cross-bucket/output-write refusals avoid echoing bucket ids or
operator filesystem paths.

Closure assessment: `W12.P26.S236` can close as `plaintext-exception`.

## S237-051 | PASS | Modelo history manifest-discovery closeout verified

The `W12.P26.S237` review found that `src/aeat/application/modelo/_history.py`
is a read-only assembly surface over injected work-unit, calculation,
verification, and bucket-event repositories. It does not construct storage
backends, inspect environment variables, write plaintext side stores, or own
secure-object routing.

The missing work-unit refusal is locale-backed with structured context, and the
step record plus affected-file register close `AFR-135` as `manifest-discovery`.
The S237 checkbox was closed through the plan CLI after the implementation commit
left the register closed but the step line unchecked.

Closure assessment: `W12.P26.S237` can close as `manifest-discovery`.

## S240-052 | PASS | Operator-surface contract/model manifest-discovery closeout verified

The `W12.P26.S240`/`W12.P26.S243` review found that
`src/aeat/application/operator_surface/_contract.py` builds cached in-memory
`OperatorSurfaceContract` records and
`src/aeat/application/operator_surface/_models.py` defines strict frozen
Pydantic contract records and enums. Neither file constructs storage
repositories, selects secure storage backends, builds SQL routes, inspects
environment variables, opens files, writes plaintext side stores, or mutates
bucket state.

Vaultspec RAG semantic searches were used for duplication review. The coupled
implementation enrolled the real `config bucket history` CLI family as a
read-only mounted command family and added the required bucket domain enum,
keeping the operator-surface architecture contract aligned with the CLI without
adding storage ownership.

Closure assessment: `W12.P26.S240` and `W12.P26.S243` can close as
`manifest-discovery`.

## S241-053 | PASS | Operator-surface CRUD contract manifest-discovery closeout verified

The `W12.P26.S241` review found that
`src/aeat/application/operator_surface/_crud_contract.py` defines enums,
Pydantic models, validation rules, and lookup helpers for mutating noun-group
shape. It has no path IO, repository construction, settings or environment
access, remote provider access, logging/printing, or exception swallowing.

Vaultspec RAG semantic searches were used for duplication review. The module
clusters with the operator-surface CRUD registry/tests and adjacent
operator-surface contract records; the previous `plain-file` signal was stale
and is corrected to `manifest-bucket`/`manifest-discovery`.

Closure assessment: `W12.P26.S241` can close as `manifest-discovery`.

## S242-054 | PASS | Operator-surface help manifest-discovery closeout verified

The `W12.P26.S242` review found that
`src/aeat/application/operator_surface/_help.py` builds strict in-memory
`HelpDocument` and `RootLandingReport` records from locale strings and caller
profile-state input. It does not construct repositories, select storage
backends, build SQL routes, read settings or environment variables, open files,
write plaintext side stores, call remote providers, or swallow exceptions.

Vaultspec RAG semantic searches were used for duplication review. The help
surface remains the presentation companion to the operator-surface contract;
the config help now advertises the already-enrolled `aeat config bucket history`
read-only bucket inspection path.

Closure assessment: `W12.P26.S242` can close as `manifest-discovery`.

## S244-055 | PASS | Overview runtime-default closeout verified

The `W12.P26.S244` review found that
`src/aeat/application/overview/__init__.py` builds in-memory overview calendar,
applicability, and filing-advisory projections. It does not contact remote
providers or create a remote mirror. Status reads persisted facts by delegating
to the canonical runtime-backed `build_operator_state_projection`, so the
affected-file register correctly closes the row as `runtime-default`.

Vaultspec RAG semantic searches were used for duplication review. Overview
clusters with agenda, backlog, CLI overview, and operator-state projection
surfaces; runtime state aggregation remains delegated through
`build_operator_state_projection` instead of duplicated in overview.

Narrow graceful-degradation paths now emit debug diagnostics before continuing,
invalid profile facts used for filing-obligation advisories are logged by field
name and error type without echoing raw operator-provided values, and central
decimal coercion no longer logs raw malformed values.

Closure assessment: `W12.P26.S244` can close as `runtime-default`.

## S245-056 | PASS | Registry plaintext-exception closeout verified

The `W12.P26.S245` review found that
`src/aeat/application/registry/__init__.py` reads registry roots, source roots,
workbook reports, scenario files, and parity tapes selected by the operator or
resolved from bundled resources. Its plaintext writes are explicit workbook
verification and parity artifacts, not profile bucket state.

Filed-state verification delegates captured filed observation reads to
`FiledDeclaracionObservationStore`, which routes through the active-bucket
secure-object repository. The stale application-layer `master_key_provider`
parameter was removed from registry verification because this layer does not
own master-key selection.

Invalid oracle environment refusals now use `RegistryApplicationInputError`
with a locale key and structured context, and registry CLI tests use
centralized configured AEAT URL helpers instead of a literal host string.

Closure assessment: `W12.P26.S245` can close as `plaintext-exception`.

## S246-057 | PASS | Registry corpus plaintext-exception closeout verified

The `W12.P26.S246` review found that
`src/aeat/application/registry/_corpus.py` reads configured manual roots,
bundled topic resources, and normative/manual corpus files through centralized
settings and domain loaders. It does not persist corpus state, profile state,
secure objects, master-key material, or remote provider mirrors.

Registry corpus refusals now use `RegistryApplicationInputError` with locale
keys and structured context for topic locale, manual section, manual id, and
manual rule-kind failures. Tests assert durable translation keys and context
rather than raw English message substrings.

The locale audit also exposed missing Modelo work CLI keys from adjacent
`tr(..., default=...)` call sites. Those keys were enrolled through
`python -m aeat.locales` so the full catalog gate passes.

Closure assessment: `W12.P26.S246` can close as `plaintext-exception`.

## S247-058 | PASS | Repair integrity runtime-default closeout verified

The `W12.P26.S247` review found that
`src/aeat/application/repair_integrity.py` probes secure-object namespaces
through the runtime-bound active-bucket repository path and persists
repair-remediation decisions as AUDIT-class encrypted secure-object rows in the
registered repair-decision namespace.

The module owns no plaintext side store, direct environment wrangling, or remote
provider mirror. Its defensive active-bucket session fallback already emits
debug diagnostics; the namespace-list fallback was removed so storage failures
propagate from the repository boundary instead of being silently swallowed.
Repair-list and repair-decision refusal paths now use locale keys and structured
context, with real repository tests covering the decision paths.

Closure assessment: `W12.P26.S247` can close as `runtime-default`.

## S248-059 | PASS | Review adapters manifest-discovery closeout verified

The `W12.P26.S248` review found that
`src/aeat/application/review/_adapters.py` loads transaction, invoice, and
filing draft review sources through domain repositories and active-profile /
bucket runtime paths. It does not persist review state, mutate source records,
write plaintext sidecars, or call remote providers.

Transaction, invoice, and filing-draft source-load wrappers now use localized
message keys with bounded `error_type` context instead of carrying raw backend
exception text in operator-facing errors. Tests exercise malformed encrypted
secure-object payloads through real active-bucket repositories.

Closure assessment: `W12.P26.S248` can close as `manifest-discovery`.

## S268-060 | PASS | User-profile orchestration runtime-default closeout verified

The `W12.P26.S268` review found that
`src/aeat/application/user_profile/_orchestration.py` coordinates profile lifecycle
storage sessions and delegates secure-object writes to profile repositories,
lifecycle services, and bucket-event repositories. It does not introduce an alternate
secure-object store, direct environment route, or duplicated storage-session factory.

The active-profile pointer and bucket directory surfaces remain centralized through
settings, bucket path helpers, and bucket-pointer IO. The intentional missing-record
degradation in `read_active_profile` now emits debug evidence before returning `None`,
and bucket-directory removal refusal now raises an AEAT user-profile error with a
locale key rather than a bare path-rendering `OSError`.

Vaultspec RAG semantic searches were used for duplication review. Focused tests use a
real lifecycle storage span and real pointer/runtime behavior, with no fake repository
or monkeypatch shortcut.

Closure assessment: `W12.P26.S268` can close as `runtime-default`.

## S270-061 | PASS | User-profile secure repository runtime-default closeout verified

The `W12.P26.S270` review found that
`src/aeat/application/user_profile/_repository.py` owns the encrypted user-profile
value and snapshot namespaces but delegates default physical repository construction to
the bucket storage runtime. It uses registered namespace constants, strict `Envelope`
records, and domain user-profile models rather than duplicating storage routing or
record shapes.

Missing profile-value and profile-snapshot loads now raise the existing AEAT
user-profile error classes with registered translation keys and structured context
instead of raw English messages. Best-effort output-language cache invalidation remains
non-blocking for persistence but now emits debug diagnostics when it is intentionally
ignored.

Vaultspec RAG semantic search was used for duplication review. Focused tests assert the
translation keys and context through real secure-object repositories and preserve the
strict roundtrip and drift tests.

Closure assessment: `W12.P26.S270` can close as `runtime-default`.

## S271-062 | PASS | User-profile testing helper runtime-default closeout verified

The `W12.P26.S271` review found that
`src/aeat/application/user_profile/_testing.py` is a thin test convenience over
canonical profile orchestration. It delegates to `register_active_profile`,
`select_profile`, and `set_active_fields`, and does not construct fake repositories,
monkeypatch storage, read environment variables, or write profile state through an
alternate backend.

The helper reuses `nif_check_letter`, the core manual-provenance constant, and
`IVARegime.GENERAL`, so it no longer carries the previously observed duplicate NIF
letter or provenance/IVA literals. Vaultspec RAG semantic search was used for
duplication review and clustered the helper with real profile-registration call sites.

Focused pointer and output-language tests passed.

Closure assessment: `W12.P26.S271` can close as `runtime-default`.

## S272-063 | PASS | Verification plaintext-exception closeout verified

The `W12.P26.S272` review found that
`src/aeat/application/verification/_verify.py` loads calculation registry snapshots
through the bundled resources authority or a caller-supplied registry-root override. It
does not persist declaration state, profile state, secure objects, master-key material,
or remote provider mirrors.

Registry policy, missing-binding, snapshot-load, and declaration-period mapping
failures now use AEAT exception classes with locale keys and bounded structured context
instead of raw English `str(exc)` wrappers or formatted plaintext exception messages.
The locale catalogue entries were added through `python -m aeat.locales`, and the
focused tests exercise the real bundled registry behavior without monkeypatching or
duplicating calculation logic.

Vaultspec RAG semantic search was used for duplication review and clustered the slice
with the verification boundary and its tests only. Focused verification tests, ruff,
and locale audit passed.

Closure assessment: `W12.P26.S272` can close as `plaintext-exception`.

## S273-064 | PASS | Wizard command manifest-discovery closeout verified

The `W12.P26.S273` review found that
`src/aeat/application/wizard/_commands.py` is a command orchestration layer over the
canonical profile storage spans. Create and full-edit flows enter
`profile_create_storage_span` or `profile_storage_session`; patch-edit flows enter
`profile_storage_session` before updating workflow state. The module does not construct
repositories, manage master-key material, write bucket manifests directly, or persist
wizard state through a side store.

Existing-profile edit mode resolves the operator label through registered-profile
guards and `read_profile_bucket`, then persists using the resolved immutable bucket id.
Output-language defaults and overrides route through settings (`load_settings` and
`override_settings`), and wizard refusals use `WizardMissingFlagError` locale keys with
structured context.

Vaultspec RAG semantic search was used for duplication review and clustered the slice
with the canonical profile storage span and profile-bucket scan helpers. Focused wizard
command and pointer-atomicity tests passed.

Closure assessment: `W12.P26.S273` can close as `manifest-discovery`.

## S274-065 | PASS | Wizard persistence manifest-discovery closeout verified

The `W12.P26.S274` review found that
`src/aeat/application/wizard/_persistence.py` is a projection layer from typed wizard
answers to `UserProfileFact` records. Create and edit persistence delegate to
`register_active_profile` and `set_active_fields`; the module does not construct
repositories, open bucket paths, write bucket manifests, manage master-key material, or
persist wizard state through a plaintext side store.

The `Path` import is type-level wizard answer handling only: it canonicalizes and
rehydrates PATH answers and performs no direct file IO. The edit-mode misuse refusal
raises `WorkflowInputMismatchError` with a locale key. No broad exception swallowing or
naked environment reads were found.

The patch path now also fails closed when a supplied question id is not declared by the
flow, raising `WorkflowInputMismatchError` with a locale key and bounded context instead
of silently skipping the unexpected id.

Vaultspec RAG semantic search was used for duplication review and clustered the slice
with wizard persistence, wizard command orchestration, canonical user-profile
registration helpers, and pointer-atomicity tests. Focused persistence and setup
runtime tests passed.

Closure assessment: `W12.P26.S274` can close as `manifest-discovery`.

## S275-066 | PASS | Wizard prompter plaintext-exception closeout verified

The `W12.P26.S275` review found that
`src/aeat/application/wizard/_prompter.py` owns prompt rendering only. It dispatches
wizard widgets to questionary primitives, returns canonical-token strings, and routes
progress through structured logging. It does not construct storage repositories, write
bucket manifests, manage master-key material, read environment variables, or persist
plaintext side files.

Interactive unsupported-console failures already raise `WizardUnsupportedConsoleError`
with locale keys and preserve the prompt-toolkit exception as the diagnostic cause.
Scripted prompter underflow and overflow paths now also raise registered AEAT wizard
exceptions with locale keys and bounded context rather than raw English messages.

Vaultspec RAG semantic search was used for duplication review and clustered the slice
with wizard prompter errors, questionary smoke tests, locale registry keys, and wizard
command orchestration. Focused prompter, setup-runtime, and questionary smoke tests
passed.

Closure assessment: `W12.P26.S275` can close as `plaintext-exception`.

## S276-067 | PASS | Wizard status manifest-discovery closeout verified

The `W12.P26.S276` review found that
`src/aeat/application/wizard/_status.py` projects workflow/profile readiness and does
not own secure-storage persistence. It does not construct repositories, write bucket
manifests, manage master-key material, read environment variables, or persist plaintext
side files.

Active profile resolution delegates to `WorkflowState.active_profile_record()` and
`resolve_active_bucket_id()`, while manifest discovery remains in workflow/core profile
bucket helpers. The status module consumes the active-profile contract and does not
duplicate manifest scanning.

Projection failures are wrapped in `WizardStatusError` with locale keys and bounded
context. The only local `except` catches `pydantic.ValidationError`, preserves the cause,
and surfaces a localized refusal. Focused status, active-profile resolution, and
profile-bucket scan tests passed.

Closure assessment: `W12.P26.S276` can close as `manifest-discovery`.

## S277-068 | PASS | Wizard translations remote-mirror closeout verified

The `W12.P26.S277` review found that
`src/aeat/application/wizard/_translations.py` is a local locale-coverage audit helper.
It walks wizard descriptors and CLI source translation keys, then resolves them through
`tr(...)`. It does not construct repositories, write bucket manifests, manage master-key
material, read remote-provider state, or mirror payloads.

The module's `Path` usage is limited to local CLI Python source introspection for
translation-key discovery. Locale catalogue drift for modelo work-creation refusal keys
was repaired through `python -m aeat.locales`, and the stale
`relation_not_decimal` locale entry was removed by the scaffold/audit flow.

Focused translation tests, ruff, locale audit, and RAG duplication search passed.

Closure assessment: `W12.P26.S277` can close as `remote-mirror`.
