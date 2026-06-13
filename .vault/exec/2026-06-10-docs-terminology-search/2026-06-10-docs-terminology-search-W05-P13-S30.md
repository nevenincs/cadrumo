---
tags:
  - '#exec'
  - '#docs-terminology-search'
date: '2026-06-10'
modified: '2026-06-10'
step_id: 'S30'
related:
  - "[[2026-06-10-docs-terminology-search-plan]]"
---




# Build the held-out real-query miss-rate harness over the compiled mapping and adjudicate the deferred rung-2 static term-embedding matrix on measurements, persisting the adjudication in the vault (ADR D6 deferral gate)

## Scope

- `dev docs tests + .vault adjudication record`

## Description

- Added a committed held-out query corpus under the terminology bundled data tree, separate from the sweep runner.
- Added a typed miss-rate evaluator over the committed `SweepResult` relevance mapping.
- Added rung-2 adjudication logic that separates degraded sweep input from genuine semantic miss evidence.
- Added real-behaviour tests that load the committed held-out corpus, compiled vocabulary, and relevance artifact.
- Persisted the rung-2 adjudication as a vault audit record.

## Outcome

S30 is satisfied. The standing held-out harness measures the current compiled mapping as 5 cases, 1 hit, 4 misses, and an 80.00% miss-rate. The committed relevance artifact also records 76 failed sweep queries and only 1 targeted query, so the adjudication is `refresh-relevance-first`: do not implement the deferred rung-2 static term-embedding matrix from this measurement. The next valid decision point is a full relevance refresh after the resident RAG service is free; only a non-degraded artifact with miss-rate above the 20% threshold justifies rung-2.

Files touched for this step: `dev/docs/terminology/_miss_rate.py`, `dev/docs/terminology/__init__.py`, `dev/docs/terminology/tests/test_miss_rate.py`, `src/aeat/_data/terminology/evaluation/held-out-queries.json`, `.vault/audit/2026-06-12-docs-terminology-search-rung2-adjudication-audit.md`, and this exec record.

## Notes

Verification run:

- `uv run pytest dev/docs/terminology/tests/test_miss_rate.py -q`: 4 passed.
- `uv run pytest dev/docs/terminology/tests/test_miss_rate.py dev/docs/terminology/tests/test_relevance_data.py dev/docs/terminology/tests/test_sweep.py -q`: 21 passed, 1 deselected.
- `uv run pytest dev/docs/terminology -q`: 89 passed, 1 deselected.
- `uv run ruff check dev/docs/terminology`: passed.
- `uv run ruff format --check dev/docs/terminology`: passed.
- `uv run ty check dev/docs/terminology/_miss_rate.py dev/docs/terminology/tests/test_miss_rate.py dev/docs/terminology/__init__.py`: passed.
- `uv run pytest src/aeat/tests/test_wheel_bundles_corpus_and_registry.py -q`: 4 passed.
- `uv run python -c 'from dev.docs.terminology import adjudicate_rung2, evaluate_held_out_miss_rate; e=evaluate_held_out_miss_rate(); a=adjudicate_rung2(e); print(f"cases={e.case_count} hits={e.hit_count} misses={e.miss_count} miss_rate={e.miss_rate:.2%} failed_queries={e.compiled_failed_query_count} targeted_queries={e.compiled_targeted_query_count} decision={a.decision.value}")'`: `cases=5 hits=1 misses=4 miss_rate=80.00% failed_queries=76 targeted_queries=1 decision=refresh-relevance-first`.

The shared worktree still contains unrelated dirty files from other workstreams. They were not modified for S30.
