---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-02'
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

## S102-011 | HIGH | OPEN | Final runtime rollout disposition proof still has unchecked W12.P26 rows

The `W12.P25.S102` review cannot close. After the S119-S128 continuation, the plan still has 226 unchecked W12.P26 affected-file closeout rows, and the affected-file register still has 229 rows marked `pending`.

This is the exact surface S102 must prove: 49 `runtime-default`, 77 `manifest-discovery`, 13 `bootstrap-custody`, 36 `plaintext-exception`, 50 `remote-mirror`, and 1 `retired` row remain unchecked. Three checked locale rows also still have pending AFR status and no local S393-S395 evidence artifact.

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
