---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:f2b2dac0aef88e16d23dd2a83b06002044c2b534992a640bd0996d4f3a0afa86'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
  - "[[2026-08-25-tui-architecture-s170-remediation-review-audit]]"
---

# `tui-architecture` audit: `S170 final follow-up review`

## Scope

Follow-up evidence record for `W03.P20.S170` after the corrective remediation
was split across shared-branch commits. It audits the committed scanner and
declarative gates at current source snapshot `976d47eb75`, records the exact
current validation results, and prepares the evidence for an independent
clean-HEAD review. It does not replace that review and does not authorize a
plan-state transition.

The first remediation audit, corrected execution record, and resident RAG
classifier were unintentionally absorbed into concurrent registry relocation
commit `c94133f295`. The remaining scanner API, declarative fixed-point gate,
and obsolete shipped-test deletion landed explicitly in `80980d90f5`. Rewriting
shared history would have risked concurrent work, so this audit supersedes the
earlier recommendation that those paths land atomically and makes the split
provenance explicit.

## Findings

### split-remediation-provenance | medium | Shared-branch concurrency prevented the planned atomic remediation commit

Commit `c94133f295` contains the corrective audit, execution correction, and
resident-search ownership classifier alongside registry relocation work.
Commit `80980d90f5` contains only the remaining S170 scanner convergence,
declarative gate update, and deletion of the obsolete shipped fixed-point
test. The resulting source state is reviewable, but provenance consumers must
judge both commits rather than infer one atomic S170 change.

### fixed-point-current-head | low | The reusable scanner and both declarative gates pass at the reviewed snapshot

Ruff passed for the scanner and both S170 test modules. The two fixed-point
modules completed with 9 passing tests in 117.31 seconds. Their live inventory
uses the scanner-owned tracked-file census, and exact mutants cover the
repository-load dataflow and dynamic export shapes identified by the prior
review.

### resident-rag-current-head | low | The enrolled S170 resident query passes directly and rejects mixed ownership

The pure classifier unit proof passed. The resident-service-marked S170 query
also passed directly at explicit port `8766` in 2.88 seconds, requiring the
canonical public owner and no parallel production owner. The complete resident
lane ran 13 tests: 12 passed and one terminology sweep failed before completing
its registry-backed materialisation because current Modelo 200 registry data
contains overlapping 2024/2025 deadline coordinates and source references
outside the selected revision authority. That failure is outside the S170
scanner and discovery surface and is not represented as a green lane.

### global-hygiene-current-head | medium | Shared import-hygiene debt prevents a repository-wide green claim

The focused scanner and import-hygiene suite completed 75 passing tests and 5
failures. The failures report 132 production cross-package private imports
against a hard-zero baseline, 103 test-only private reaches, and 11 debt entries
that no longer answer live occurrences. These are shared repository state after
the registry/public-module transition, not changes introduced by the S170
commits. They remain blockers to describing the complete hygiene gate as green.

## Recommendations

Keep `W03.P20.S170` unchecked. An independent reviewer must inspect the combined
state from `c94133f295` and `80980d90f5`, rerun the S170 fixed-point and direct
resident query proofs, verify the obsolete shipped test remains absent, and
adjudicate whether the unrelated resident-lane registry-data failure and global
import-hygiene failures prevent a PASS disposition. Only a subsequent review
may recommend closing S170.
