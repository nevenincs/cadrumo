---
tags:
  - '#audit'
  - '#user-docs-search-consolidation'
date: '2026-08-06'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:3e0241986b8ab4465cff1ac6d32333fa855f223521c64a41ebd8e99530b02c1c'
related:
  - "[[2026-08-01-user-docs-search-consolidation-adr]]"
---

# `user-docs-search-consolidation` audit: `P02.S32 formal code review`

## Scope

Reviewed the independent Rung-2 query/alias authority, its committed data artifact, Handbook anchoring and held-out rejection, sweep union, input parity, nested raw-byte provenance, Python bundle propagation, browser validator contract, and direct real-behaviour tests. The review was grounded by fresh vaultspec-rag searches against ADR Update 11 and the current input/provenance/browser seams.

## Findings

### P02.S32 formal code review | low | authority schema is strict and independently bounded

PASS. The exact schema literal, positive authority version, ratified-only rows, frozen extra-forbid models, deterministic ordering, and raw-byte source identity are implemented. The committed authority has zero entries because no independently ratified non-held-out alias was evidenced; no alias was invented or copied from evaluation data.

### P02.S32 formal code review | low | Handbook and held-out boundaries fail closed

PASS. Authority entries must name an approved Handbook concept, anchor to a same-language current Handbook query, avoid normalized collisions, and avoid held-out query text. The integration checks the committed relevance mapping against the Handbook-plus-authority union before matrix work.

### P02.S32 formal code review | low | nested provenance is carried through the typed bundle

PASS. `Rung2InputProvenance` requires the nested authority path/schema/version/raw digest alongside the relevance source digest and derived fingerprints. The existing typed bundle serializes that nested field and the Python acceptance tests pass.

### P02.S32 formal code review | low | browser provenance contract was corrected

PASS after the review finding was repaired in P02.S33. The browser validator now requires and validates the nested authority identity and rejects the pre-amendment flat-only shape, while the semantic tier remains disabled without accepted evidence.

### P02.S32 formal code review | low | shared-worktree and test fidelity are acceptable

PASS. The implementation preserves unrelated peer WIP, uses direct production imports, and uses no mocks, fakes, stubs, monkeypatching, skips, or xfails. Focused Rung-2 coverage recorded 61 passed; the isolated browser rerun recorded 1 passed. Ruff, basedpyright, node syntax, and diff checks are clean.

### P02.S32 formal code review | low | acceptance status is honest

PASS. The live RAG refresh recorded 112 queries, 49 concepts, 0 failures, and 112 targeted queries; the held-out baseline remains 26/32 with a 0.1875 miss rate. No matrix, browser enablement, release, or deployment is claimed.

Review verdict: PASS. No actionable code-review findings remain.

### P02.S32 formal code review | low | supplied authority models are bound to raw bytes

PASS after follow-up hardening. The provenance builder reloads the committed JSON and rejects a caller-supplied authority model whose version or entries differ from those raw bytes; the direct tamper test passes.

## Recommendations

Keep P02.S32 open until an independently ratified alias set (if needed), a Rung-2 matrix, the accepted ladder measurement, and the existing browser/release gates are actually produced and pass. The P02.S33 browser provenance seam is closed with its recorded isolated browser proof. Deployment remains outside this review.
