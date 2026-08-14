---
tags:
  - '#audit'
  - '#profile-password-custody'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:228f3e324ea8dae286d7c25270a9d152c665822a363c5ef642598f6d5321ff89'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
  - "[[2026-08-13-profile-password-custody-rollup-adr]]"
---



# `profile-password-custody` audit: `S06 integrated custody phase review`

## Scope

Phase-ending independent joint review of `W01.P02.S03` through `W01.P02.S05`: the accepted custody ADR and research, execution records and prior audits, supervised KDF and IPC containment, password/recovery/sentinel domains, capsule publication, application create/delete transactions, pointer locking, hold owners, receipts, hostile-filesystem boundaries, local-only scope, negative dependency searches, and real-behavior verification. This review authorizes no production edits, configured storage, remote or service action, Git action, later Step, or plan check unless every critical/high finding is closed on a stable candidate.

## Findings

### create-publication-integration | high | The create journal cannot currently precede the only capsule publication operation

`ProfileCustodyTransactionService.prepare_create` says it journals before publication but requires a caller-supplied proposed inventory digest and staged relative path. The only capsule publisher, `publish_profile_custody_capsule`, internally creates the sibling stage, writes and fsyncs every member and marker, and atomically renames it before returning; it exposes no prepared-stage or pre-publication journal seam. Repository search finds no production caller composing create preparation, publication, and recovery. The test publishes the final capsule first, then creates the journal and calls recovery, so it cannot prove the accepted journal-before-publication or rename-before-journal crash boundaries. Introduce one application-owned create orchestration that derives rather than trusts stage/generation/digest, durably journals before final publication, and invokes a transaction-bound staged publisher under the root/profile locks; prove crashes before journal, after journal/before rename, after rename/before journal state, and after pointer CAS. Do not require callers to reproduce capsule inventory logic.

### unstable-supervision-refactor | high | The current custody worker import is broken and the focused lane no longer executes

During the review the custody surface changed: spawned interpreters importing `_kdf_supervision.py` raise `NameError` because `ProfileCustodySentinelRecord` still subclasses `BaseModel` after that import was removed. The resulting worker EOFs surface as `KDF_SUPERVISION_UNAVAILABLE`, and sibling transaction/CAS tests time out because their spawned imports fail. The combined custody/S05 run currently reports 12 failures and 44 passes. The new `_sentinel_contract.py` also fails Ruff for unsorted imports and an unused `Path`. Complete the sentinel-contract migration so every parent and spawned-child import resolves one canonical record/verification implementation, rerun the real Windows worker, capsule, sibling lock and CAS lanes, and refreeze the bytes before final S06 adjudication.

### partial-negative-audit | info | No prohibited testing shortcut or direct retired provider dependency was found before the refreeze pause

The scoped negative search found no fake, stub, mock, monkeypatch, skip, or xfail shortcut in the S03-S05 focused tests, and no direct `master_key` or legacy-provider import in the custody package or `_custody_transactions.py`. Expected fixed-module subprocess use is confined to the supervised KDF implementation and its real-process tests. Final negative and static evidence must be repeated on the refrozen candidate.

### supervision-refactor-closure | info | The canonical sentinel contract and worker import boundary are restored

The refrozen worker imports `ProfileCustodySentinelRecord` and its verifier from the sole `_sentinel_contract.py` implementation; the stale local `BaseModel` definition is gone. Direct compilation succeeds for the worker, sentinel, capsule, and transaction modules. Ruff, ty, and basedpyright are clean across the integrated S03-S05 surface. The executor's immediately preceding frozen run exercised 17 real worker tests and the combined 56-test custody/transaction lane successfully. The independent rerun is presently collection-blocked before custody import by an unrelated peer registry constant mismatch, not by the custody modules; that limitation is recorded rather than represented as a green rerun. This closes `unstable-supervision-refactor` on source, static, compilation, and the frozen handoff's real-process evidence.

### create-publication-integration-closure | info | One application owner now journals and verifies the durable stage before final publication

`ProfileCustodyTransactionService.create_capsule` now derives the transaction UUID, canonical sibling-stage name and envelope generation; captures the pointer and durably creates `PREPARED` before staging; invokes the capsule writer in stage-only mode; inventories and binds the complete durable stage into `STAGE_VERIFIED`; performs the sole no-replace stage-to-final rename; records `CAPSULE_PUBLISHED`; and compare-and-swap publishes the pointer last before receipt completion. Recovery distinguishes intent-only, unverified stage, verified stage, and final-after-rename states, refuses stage/final ambiguity and foreign identities, and never accepts a final capsule from a merely `PREPARED` journal. The caller-authored `prepare_create` API is removed. Real spawned-process tests terminate at intent, stage, verify and rename boundaries and recover each attributable state. This closes `create-publication-integration`.

### s06-integrated-pass | info | No critical or high finding remains across the S03-S05 phase

The integrated architecture review rechecked finite-grid calibration and fail-closed supervision; ready-before-secret and process/handle containment; password, recovery, artifact and sentinel domains; immutable epoch and capsule publication; canonical bounded journals; root/profile locks and exact pointer CAS; create and deletion crash recovery; independent hold owners; confirmation and effect-bound receipts; local-only retained-external reporting; no direct retired-provider dependency; Windows and POSIX hostile-path branches; and real non-tautological tests. The refrozen handoff reports 56 combined custody/transaction tests, 22 pointer/orchestration/session tests, and 58 taxonomy tests passing. The independent current static and compilation gates are clean. The only unavailable independent runtime rerun is blocked during unrelated registry package collection by missing `_EXTRACTOR_VERSION`; it neither executes custody code nor contradicts the immediately preceding frozen custody results.

## Recommendations

PASS. No critical or high finding remains. Create the `W01.P02.S06` execution record and close only S06 through the canonical VaultSpec plan command. Record the unrelated registry collection limitation explicitly; do not claim a whole-repository green run and do not start `W02.P03.S07`.
