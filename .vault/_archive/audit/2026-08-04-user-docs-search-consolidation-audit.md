---
tags:
  - '#audit'
  - '#user-docs-search-consolidation'
date: '2026-08-04'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:6631dadff889f8e3e78146b447457f441179d7f46a11d31c911fbffd00e4b7b0'
related:
  - "[[2026-08-01-user-docs-search-consolidation-plan]]"
---

# `user-docs-search-consolidation` audit: `P01.S01 shipped search licence rule amendment`

## Scope

Audit the P01.S01 licence-rule amendment and its provider propagation against the accepted UserDocs R5 decision and the executable plan, before any rung-2 implementation is dispatched.

## Findings

### p01-s01-scope | low | Rule amendment matches the accepted R5 boundary

Read-only review of the accepted ADR, plan, and live rule diff found no scope defect. The amendment permits only a reviewable plain-data term-embedding matrix in built documentation, never the wheel, from a pinned named MIT or Apache-2.0 model over project vocabulary with model, revision, licence, vocabulary-fingerprint, and serialized-size provenance and a 3 MB ceiling. The NC/ND/gated-source, raw-oracle-output, raw-vector, and generated-index prohibitions remain explicit.

### p01-s01-propagation | low | All generated provider copies are synchronized

The source and five generated provider outputs carry the same amended rule body, and a non-mutating `vaultspec-core sync --dry-run --json` returned `status: unchanged`. The focused VaultSpec health check found no structural, frontmatter, link, body-section, or execution-mapping diagnostics for this feature. No unrelated implementation path is part of the UserDocs delta.

## Recommendations

- Keep the P02.S06 licence gate as the enforcement point for the provenance fields and 3 MB bound recorded by P01.S01; this review does not treat prose policy as runtime validation.
