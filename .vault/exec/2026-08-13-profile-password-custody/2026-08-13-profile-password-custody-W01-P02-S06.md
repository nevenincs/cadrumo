---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:20423b23e8f75ff9ab966a6845b031874fb7429c812e33aa30394bd0bd755c72'
step_id: 'S06'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---




# Have Sol Medium jointly review KDF calibration and supervision, envelope and artifact AAD, capsule publication, journal recovery, and application-owned local deletion safety

## Scope

- `src/cadrumo/adapters/persistence/storage/custody/ and src/cadrumo/application/user_profile/`

## Description

- Reviewed the accepted custody ADR and research plus the S03-S05 execution records and independent rolling audits.
- Reconciled the finite Argon2id grid, supervised ready-before-secret worker, framed DEK-only result, operating-system containment, sentinel proof, password and recovery AAD domains, and immutable epoch contract.
- Reviewed canonical recovery artifacts, password-only normal reads, hostile-path handling, complete staged capsule durability, no-replace publication, current-marker recognition, and platform-specific Windows/POSIX filesystem boundaries.
- Reviewed bounded canonical create/delete journals, root-before-profile locks, exact pointer CAS, transaction-owned create staging and publication, destructive confirmation, hold-owner projections, owner effects and receipts, crash recovery, and local-only external-state reporting.
- Repeated negative searches for prohibited test shortcuts and direct retired-provider dependencies, plus focused static and compilation gates.
- Adjudicated and closed the integrated create-publication and sentinel-worker regressions in the S06 audit before approving the phase.

## Outcome

The integrated S03-S05 custody phase passes architecture and code review with no unresolved critical or high finding. Create now has one application-owned journal-before-stage, verify-before-rename, pointer-last orchestration with recovery for intent, stage, verified and renamed crash states. The KDF worker and canonical sentinel contract import and compile cleanly, and static gates pass across the integrated surface.

Verification evidence on the refrozen candidate:

- Frozen executor run: 56 combined custody/transaction tests passed, including the real subprocess create crash matrix.
- Frozen executor run: 22 pointer/orchestration/session tests passed.
- Frozen executor run: 58 storage-taxonomy tests passed.
- Frozen executor run: 17 isolated real KDF worker tests passed.
- Independent review: Ruff and ty clean; basedpyright reported zero errors, warnings or notes; direct Python compilation of the worker, sentinel, capsule and transaction modules passed.

## Notes

The first integrated attempt exposed a broken in-progress sentinel refactor and the absence of a journal-before-publication create orchestration. Both were remediated and re-reviewed. The current independent pytest rerun is blocked before custody collection by an unrelated concurrent registry import mismatch: `_m303_orden_manifest.py` imports missing `_EXTRACTOR_VERSION` from `_m303_orden_constants.py`. This is not reported as a green whole-repository run and was not treated as custody failure or success; the PASS relies on current source/static/compile review and the executor's immediately preceding refrozen real-process results. No production code, configured storage, remote or service state, Git state, or later plan Step was changed by this review.
