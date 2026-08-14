---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:bbb49fb5c1002ad84876f7e0dc48003a5b5fcad7e51c1c3838fb54368b403057'
step_id: 'S05'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh implement custody and deletion journals, root-profile locks, no-follow inventory, legal-hold confirmation, receipts, pointer CAS, and atomic deletion

## Scope

- `src/cadrumo/application/user_profile/`

## Description

- Added bounded, canonical transaction journals and per-owner durable receipts with idempotent replay, strict recovery, and target-bound confirmation for create and local deletion.
- Added root-before-profile, OS-released custody locks; descriptor- and handle-anchored no-follow local record access; exact committed-capsule inventory; verified tombstone markers; and atomic local rename/removal recovery that refuses ambiguity.
- Added a captured-byte/digest active-pointer snapshot and compare-and-swap authority under the shared custody root lock, and moved the existing pointer transaction onto that authority to prevent interleaving overwrites.
- Ordered actual process-secret revocation and current session-acceleration cleanup ahead of pointer clearing, preserving durable receipts across crash/retry without external actions.
- Replaced caller-supplied legal/filing flags and custody-owned outcome writers with independent owner fact projections: legal case facts derive a hold from open cases, while actual `ModeloRecord` facts are evaluated by the domain retention floor. Missing or corrupt owner facts refuse deletion; refreshed source digests bind confirmation and execution revalidation.
- Added real filesystem, hostile-link/reparse, transaction ambiguity, receipt replay, owner-effect, sibling-process lock, no-replace, pointer interleaving, and owner-fact drift coverage.

## Outcome

`W01.P02.S05` now provides the application-owned current-format local custody transaction authority. Create recovery accepts only the exact transaction-bound staged or committed capsule and publishes the pointer last. Deletion is local-only and proceeds only after exact inventory, independently derived legal and filing clear facts, target-bound confirmation, process/session cleanup, and pointer CAS; all other ambiguity, drift, absent evidence, link/reparse, and persistence failures refuse safely. Receipts explicitly report retained external state and no remote action occurs.

Focused verification completed on Windows:

- `uv run --no-sync pytest src/cadrumo/application/user_profile/tests/test_custody_transactions.py src/cadrumo/adapters/persistence/storage/custody/tests -q` - 56 passed in 37.20 seconds.
- `uv run --no-sync pytest src/cadrumo/application/user_profile/tests/test_orchestration_pointer.py src/cadrumo/application/user_profile/tests/test_orchestration.py src/cadrumo/application/user_profile/tests/test_login_session.py -q` - 22 passed in 9.08 seconds.
- `uv run --no-sync pytest src/cadrumo/core/tests/test_storage_taxonomy.py src/cadrumo/core/tests/test_storage_liveness_gate.py src/cadrumo/core/tests/test_storage_materialisation_parity.py src/cadrumo/core/tests/test_storage_taxonomy_name_unification.py -q` - 58 passed in 4.26 seconds.
- `uv run --no-sync ruff check` over the S05 surface - clean.
- `uv run --no-sync ty check` over the S05 surface - clean.
- `uv run --no-sync basedpyright` over the S05 surface - 0 errors, 0 warnings.

Independent Sol review completed after successive hostile-filesystem, transaction-boundary, session-owner, pointer-CAS, and hold-source remediations. The final review found no unresolved critical or high finding and re-ran 23 transaction tests, 56 combined custody/S05 tests, 17 pointer regressions, and the static gates clean.

## Notes

No configured product store, remote state, service state, Git state, or later plan Step was changed. The source hold owner mutations are deliberately outside the `application.user_profile` facade; that facade exposes only custody-derived read artifacts.
