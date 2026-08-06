---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-15'
modified: '2026-07-15'
body_hash: 'sha256:da35c058160aaea12bea28feb87e928176d20a237e25987c1444bc85e9c05679'
step_id: 'S28'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Route profile-health repair mutation through the shared reentrant active-profile pointer transaction with locked reassessment, bounded fail-closed contention, and the health result's repairable flag as the sole eligibility authority, correct the three lifecycle CLI integration pointer setup calls to use the isolated backend root, then prove pointer-sourced unreadable-manifest repair, cold no-op behavior, and real CLI pointer repair, absence, and dangling-pointer outcomes

## Scope

- `src/cadrumo/application/workflow/_profile_health.py`
- `src/cadrumo/application/workflow/tests/test_profile_health.py`
- `src/cadrumo/entrypoints/cli/tests/test_profile_lifecycle_verbs.py`

## Description

- Route repair mutation through `active_profile_pointer_transaction` after a preliminary read-only assessment.
- Reassess health while holding the pointer transaction and use `repairable_by_clearing_pointer` as the sole mutation eligibility decision.
- Preserve the cold no-op path without opening a bucket session or creating pointer and lock files.
- Prove that pointer-sourced unreadable-manifest repair clears only the pointer and preserves the manifest bytes exactly.
- Bind the three lifecycle CLI pointer setup operations to the storage root yielded by `_isolated_backend`.
- Run semantic RAG grounding before implementation and review, followed by exact symbol and duplicate scans.

## Outcome

- Landed the health transaction implementation in `7c7e4b19a2` and the fixture-root correction in `9b18b4154c`.
- Focused health and resolution checks passed 14 tests; hygiene and persistence-policy checks passed 13 tests.
- Import-linter analyzed 3,422 files and 16,146 dependencies with five contracts kept and none broken.
- The three explicit lifecycle integrations initially exposed two failures and one vacuous pass against the wrong root; after correction, both author and reviewer lanes passed all three with `-m integration -n0`.
- Ruff, compilation, diff checks, post-change RAG, and exact scans passed.
- Formal review found no blocker, high, medium, or low issues.

## Notes

- The S26 lifecycle test setup regression was discovered only when the integration-marked nodes were selected explicitly; the default unit marker had deselected them.
- The peer change to the transaction error superclass remained untouched and excluded from both commits.
- S29 retains the broader real-file rollback and concurrency proof; this step makes no claim beyond its health and lifecycle integration scope.
- No data loss occurred and no runtime scaffolds were left.
