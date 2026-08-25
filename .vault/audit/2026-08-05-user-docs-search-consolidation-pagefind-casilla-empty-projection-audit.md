---
tags:
  - '#audit'
  - '#user-docs-search-consolidation'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:db7051e7d144409d10ee7486d106f90d648594600f12ed3a8644dee2d5ab488b'
related:
  - "[[2026-08-01-user-docs-search-consolidation-plan]]"
---

# `user-docs-search-consolidation` audit: `Pagefind casilla empty-projection review`

## Scope

Review the RAG-grounded fail-closed correction in `dev/docs/pagefind_inject.py` and the follow-up test-contract alignment in `dev/docs/tests/test_pagefind_inject.py`. The review covers the authoritative casilla projection, the Pagefind injection boundary, malformed relevance handling, and preservation of the Rung-2 read-only projection path.

## Findings

### casilla-projection-guard | low | Empty casilla projection could previously publish an incomplete corpus

The authoritative injection path previously allowed zero projected casilla records to proceed even though the casilla projection is exhaustive over the validated registry and the injection contract declares casillas a priority surface. LUNA Max added a guard in `_require_complete_projection()` that raises `SearchInjectionError` before relevance loading, sampling, or custom-record writes. LUNA Extra High reviewed the exact diff and returned PASS with no critical, high, medium, or low findings. Legal projection, CLI-skip handling, normal statistics, Rung-2 read-only materialisation, and Pagefind fallback behavior remain unchanged.

### relevance-fixture | low | Malformed-relevance expectation was stale and is now aligned

The production loader documents and implements fail-closed `SearchInjectionError` behavior for a present malformed relevance file. LUNA Max updated `dev/docs/tests/test_pagefind_inject.py` to import the production exception and assert the exact error from a real malformed file. LUNA Extra High reviewed the combined source/test diff and returned PASS with no findings. The test was not run because the test lane remains deferred.

## Recommendations

Keep P06.S24 and the remaining artifact/runtime verification rows open until their authorized real-behaviour evidence exists. Preserve the fail-closed casilla and relevance-loader contracts; run the aligned test only in the authorized verification lane before closure.
