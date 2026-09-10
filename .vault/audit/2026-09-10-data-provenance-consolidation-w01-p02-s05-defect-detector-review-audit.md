---
tags:
  - '#audit'
  - '#data-provenance-consolidation'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:f9c6cb5547cc9e445fb17f4b10b2f6e67a72d8cb8d1a07207dfc22b4d1bc303a'
related:
  - "[[2026-09-10-data-provenance-consolidation-plan]]"
---

# `data-provenance-consolidation` audit: `w01 p02 s05 defect detector review`

## Scope

Review W01.P02.S05 typed detector teeth for malformed, conflicting, orphaned, and unknown catalog inputs.

## Findings

### malformed-diagnostic-route | high | Malformed claims were rejected before the compiler could report a typed diagnostic

The compiler now accepts an explicit raw identity input and turns failed strict construction into `MALFORMED_IDENTITY`; direct model construction remains fail-closed.

### malformed-retrieval-date | high | A raw claim could bypass validation with a non-date retrieval value

The immutable identity now requires a date-only value and the detector test proves a datetime claim produces `MALFORMED_IDENTITY` with no published role.

## Recommendations

Adapters should keep using strict immutable identities; diagnostic consumers that need malformed declaration reporting should use the explicit raw input boundary.
