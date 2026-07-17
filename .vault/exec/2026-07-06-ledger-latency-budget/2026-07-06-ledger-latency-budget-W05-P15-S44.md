---
tags:
  - '#exec'
  - '#ledger-latency-budget'
date: '2026-07-06'
modified: '2026-07-17'
step_id: 'S44'
related:
  - "[[2026-07-06-ledger-perf-optimization-plan]]"
---

# Confirm registry authority cache behavior stays covered by the existing authority tests

## Scope

- `src/aeat/domain/calculations/registry/tests/test_authority.py`

## Description

- Ground registry cache ownership with semantic search for `registry authority cache TTL validated authority load tests`.
- Inspect `ValidatedRegistryAuthority.load`, `_load_authority`, and the authority cache tests covering snapshot reuse, fingerprint-backed process cache reuse, registry-fragment invalidation, and source-evidence invalidation.
- Confirm the residual registry-cache item is already covered by existing tests without changing registry runtime code.

## Outcome
- `uv run pytest -q -n 0 src/aeat/domain/calculations/registry/tests/test_authority.py` passed: 10 tests in 14.24s.
- No implementation change was required for this residual confirmation step.

## Notes

- RAG returned `src/aeat/domain/calculations/registry/_authority.py`, `src/aeat/domain/calculations/registry/tests/test_authority.py`, and the existing research note that registry cache tuning should remain a residual confirmation unless new scale data shows a gap.
