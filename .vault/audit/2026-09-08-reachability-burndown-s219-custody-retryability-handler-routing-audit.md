---
tags:
  - '#audit'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:a62b8796c6ad27597556dbc58720245d2b99f7a2c12a4697b516cb8ba2a3be97'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
  - "[[2026-09-04-reachability-burndown-W05-P12-S219]]"
---

# `reachability-burndown` audit: `S219 custody retryability handler routing review`

## Scope

Independent review of W05.P12.S219, limited to custody exception translation in `adapters.persistence.storage.profile_custody` and `application.user_profile.profile_repository`, the retained type/AST handler-flattening detector, focused adapter tests, and the S219 Step Record.

## Findings

No critical, high, medium, or low findings.

Both affected boundaries now route the narrower concurrent-change subtype before its non-retryable integrity parent. The persistence adapter catches `ProfileCustodyConcurrentCapsuleChangeError` before `ProfileCustodyRecordError`, translating it to `ProfileCustodyConcurrentChangeError`; other record failures become `ProfileCustodyRecordIntegrityError`. The committed-profile repository then catches `ProfileCustodyConcurrentChangeError` before `ProfileCustodyRecordIntegrityError`, translating concurrency to retryable `ProfileCustodyTransactionConflictError` and permanent integrity failure to non-retryable `ProfileCustodyTransactionCorruptError`. Exception chaining is retained at both layers.

The change repairs the semantic distinction without broadening catches or changing successful custody behavior. No mock-only, name census, allowlist, or development metastate was added. The retained gate derives divergent pairs from registered exception types, scans real handler ASTs, checks non-vacuity and package coverage, and carries both a planted flattening positive and correctly routed negative control.

The Step Record is exact for the reviewed paths and records Ruff, the focused adapter/detector suite, and the live reachability measurement. Independent execution of the same focused suite passed all 9 tests in serial isolation.

## Recommendations

Approve W05.P12.S219. Keep future retryability regressions owned by registered error semantics plus the type/AST-derived handler gate; do not reintroduce code-name or handler inventories.
