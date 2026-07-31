---
tags:
  - '#exec'
  - '#post-release-distribution'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:06e1fb02af1f630cc212da680a6e446419a177926ac1e4e09edbf25ea385dc01'
step_id: 'S31'
related:
  - "[[2026-07-17-post-release-distribution-plan]]"
---

# DONE 7d20b2d984, the docs-claims gate now measures, a positive control asserts every pattern against a must-match and a must-not-match string and a guard requires a new pattern to arrive with its own cases, the retired tap pattern fails 2 of 4 control cases so the control discriminates. GATE, uv run --no-sync pytest dev/docs/tests/test_distribution_claims.py collects 12 and passes

## Scope

- `dev/docs/tests/test_distribution_claims.py`

## Description

- Add a positive-control table pinning every claim pattern against strings that must match and strings that must not.
- Add a guard requiring each declared pattern to carry its own control cases, so a new pattern cannot silently escape coverage.
- Add a corpus-not-empty assertion, so the scan cannot pass vacuously over zero files.

## Outcome

The gate now measures. It carried two tests, neither of which passed a string to a pattern, and the corpus scan hit an early return over 59 documents containing zero claims. It was green because it was inert. The suite is now 12 tests, and the retired tap pattern fails 2 of the 4 tap control cases, which is what demonstrates the control discriminates rather than merely passing.

## Notes

My earlier claim to have verified the patterns in both directions was true of a manual evaluation I ran and untrue of the test suite. The manual check was real but it was not a gate, and nothing would have noticed it rotting. Semantic search was degraded for the whole of this work: the code index served roughly a fifth of the tree while reporting itself healthy, so a search miss was worthless as evidence. Discovery was done by direct directory listings, file reads, and targeted pattern search instead.
