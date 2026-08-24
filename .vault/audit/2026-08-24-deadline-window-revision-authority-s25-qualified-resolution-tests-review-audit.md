---
tags:
  - '#audit'
  - '#deadline-window-revision-authority'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:7b8a74e97b7cb2bbe1fd1ca5ac7abe1157b7983d72ad993051a44a1e87ea4c97'
related:
  - "[[2026-08-24-deadline-window-revision-authority-plan]]"
---

# `deadline-window-revision-authority` audit: `s25 qualified resolution tests review`

## Scope

Reviewed approved step `W03.P10.S25` against the deadline authority ADR,
research, reference, and plan. The review covered the complete diff in
`src/cadrumo/domain/deadlines/tests/test_plazo_resolution.py`, the canonical
matcher in `src/cadrumo/domain/deadlines/_plazo.py`, and semantic discovery for
parallel deadline resolvers or qualifier vocabularies. Focused pytest and Ruff
both passed.

## Findings

### s25-qualified-resolution-tests-review | low | shared-concept premise is not asserted

`test_official_codes_with_a_shared_rate_concept_remain_distinct_coordinates`
correctly proves that official codes `01` and `35` resolve to different deadline
windows, but it does not assert through `M210_TIPO_RENTA_CODE_PROJECTION` that
both codes currently map to the same canonical `TipoRentaIrnr` rate concept.
The test would therefore remain green if that load-bearing premise drifted,
weakening the specific regression promised by the step even though the resolver
distinction itself is covered.

Resolved in S25 by asserting both codes share the same concept through the
canonical `M210_TIPO_RENTA_CODE_PROJECTION` before proving their deadline
coordinates resolve independently. No mapping was copied into the test.

No critical, high, or medium findings were identified. Semantic discovery and
exact-symbol confirmation found one production resolver,
`resolve_filing_window`, one shared atomic coordinate expansion, and the existing
core `ResultDisposition` and official-code projection; this test-only change adds
no production resolver, vocabulary, or redeclaration.

## Recommendations

- For `shared-concept premise is not asserted`, add a direct assertion that
  `M210_TIPO_RENTA_CODE_PROJECTION["01"] is
  M210_TIPO_RENTA_CODE_PROJECTION["35"]` before exercising the two distinct
  deadline coordinates. Continue importing that canonical projection through
  the core facade; do not reproduce its mapping in the test.
