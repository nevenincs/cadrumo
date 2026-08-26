---
tags:
  - '#audit'
  - '#docs-terminology-search'
date: '2026-06-12'
modified: '2026-08-26'
body_hash: 'sha256:c03410f2253f4c84a2da6d57596f082876df6a12dd0f0118dec07b422c870c54'
related:
  - '[[2026-06-10-docs-terminology-search-adr]]'
  - '[[2026-06-10-docs-terminology-search-plan]]'
---

# `docs-terminology-search` audit: `rung-2 adjudication`

## Measurement

The S30 harness evaluates 5 held-out operator-query cases against the committed compiled relevance mapping. Current result: 1 hit, 4 misses, 80.00% miss-rate. The only hit is `regla de prorrata`, which resolves to the prorrata BOE/legal or concept targets. The misses are all targetless rows, not target mismatches.

The compiled relevance artifact is explicitly degraded: it records 76 failed sweep queries, 76 compiled query rows, and 1 targeted query row. The artifact provenance says the RAG service was saturated by a peer index rebuild and that the prorrata entry was seeded from the real captured service response.

## Adjudication

Decision: `refresh-relevance-first`.

The 80.00% miss-rate is not clean evidence for the deferred rung-2 static term-embedding matrix because the input mapping is already marked as a failed/partial sweep. Implementing a static matrix from this measurement would convert service saturation into a misleading architecture decision. The next action is to refresh the relevance mapping with a non-degraded resident RAG sweep, then rerun the S30 harness. If the refreshed artifact has no failed compiled queries and its held-out miss-rate remains above 20%, rung-2 becomes justified by measurement.

## Evidence

- Held-out corpus: `src/aeat/_data/terminology/evaluation/held-out-queries.json`.
- Harness: `dev/docs/terminology/_miss_rate.py`.
- Test gate: `dev/docs/terminology/tests/test_miss_rate.py`.
- Measurement command: `uv run python -c 'from dev.docs.terminology import adjudicate_rung2, evaluate_held_out_miss_rate; e=evaluate_held_out_miss_rate(); a=adjudicate_rung2(e); print(f"cases={e.case_count} hits={e.hit_count} misses={e.miss_count} miss_rate={e.miss_rate:.2%} failed_queries={e.compiled_failed_query_count} targeted_queries={e.compiled_targeted_query_count} decision={a.decision.value}")'`.
