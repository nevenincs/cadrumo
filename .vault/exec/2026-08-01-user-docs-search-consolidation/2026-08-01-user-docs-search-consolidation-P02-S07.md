---
tags:
  - '#exec'
  - '#user-docs-search-consolidation'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:7088c0232ba8c70e13e31ccc69263f3abdb6aca05d42ebafdb3637931a6e80df'
step_id: 'S07'
related:
  - "[[2026-08-01-user-docs-search-consolidation-plan]]"
---

# Re-run the held-out miss-rate measurement over the rung-2-enabled ladder and commit the report as the new standing baseline beside the 0.1875 pre-rung-2 figure

## Scope

- `src/cadrumo/_data/terminology/evaluation/`

## Description

## Description

- Re-ground P02.S07 with current vaultspec-rag searches over the held-out evaluator, report CLI, Rung-2 adjudication, and acceptance boundary.
- Inspect whether the evaluator and canonical report path are present without running the measurement or producing a report.
- Record the exact evidence prerequisite for the new post-Rung-2 baseline.

## Outcome

## Outcome

The source measurement seam is present: the held-out query corpus, evaluator, report command, and ratified-threshold adjudication are implemented. No post-Rung-2 baseline can be claimed because the required Rung-2 matrix/artifact and its acceptance evidence do not exist, and the measurement was not authorized or run. The pre-Rung-2 baseline remains the only standing measurement. P02.S07 remains unchecked.

## Notes

### 2026-08-05 source continuation: semantic-tier measurement primitive

Fresh vaultspec-rag grounding over the accepted Rung-2 contract, the browser semantic seam, the bridge, the matrix, and the existing miss-rate evaluator confirmed that the Python evaluator previously modeled only the pre-Rung-2 lexical ladder.

A disjoint source-only measurement primitive was added in `dev/docs/terminology/_rung2_evaluation.py`. It consumes an already validated `Rung2SearchBundle` plus an explicit, no-default `Rung2EvaluationPolicy`; mirrors the browser's shared normalization, covered-token multiplicity-preserving float32 mean pooling, dequantization, cosine floor, runner-up abstention, deterministic UTF-8 tie order, and manifest-backed record bridge; and returns measurement rows without URL construction, acceptance adjudication, artifact I/O, or release configuration.

This does not close P02.S07. The primitive measures the semantic tier in isolation. The required standing report still needs an authorized full-ladder composition with Pagefind/lexical results, independent float32-versus-int8 top-five-loss evidence, and the accepted post-Rung-2 artifact/config. The pre-Rung-2 0.1875 baseline remains the only standing measurement.

No tests, builds, model downloads, matrix generation, generated reports, Pagefind/runtime probes, live sweeps, RAG reindexing, deployment, or artifact release were run.

### 2026-08-05 source continuation: explicit ladder composition seam

A source-only composition seam now accepts an independently captured Pagefind observation tuple plus the validated semantic-tier result. Strict models preserve the browser ordering contract: direct lexical identity first where applicable, then tier and direct-match ordering, semantic score and ranking weight, and deterministic ties; duplicate record ids are removed after ordering and the browser result cap is retained. The seam performs no Pagefind access, artifact I/O, acceptance adjudication, or report generation. `evaluate_rung2_held_out` remains semantic-only, so P02.S07 and the 0.1875 standing baseline are unchanged.

A source review was completed manually against the RAG-grounded browser contract. AST parsing and diff checks were used as static proof only. No tests, builds, model downloads, generated reports or artifacts, Pagefind/runtime probes, live sweeps, reindexing, deployment, or release acceptance were run.

### 2026-08-05 source continuation: aggregate coverage evidence

Fresh vaultspec-rag grounding over the browser-equivalent evaluator, the matrix query-token contract, the acceptance boundary, and the P02.S04/P02.S07 records identified that per-query coverage was recorded but not aggregated into independently auditable evidence. The source-only evaluator now exposes `Rung2CoverageEvidence` and `aggregate_rung2_coverage`. The primitive validates evaluation arithmetic, rejects zero-token and over-covered rows, computes total and covered token counts, fully-covered, zero-covered, below-policy counts, and the aggregate ratio, and binds the result to the query-set version, matrix query-token fingerprint, matrix artifact hash, and bundle artifact hash.

This remains measurement evidence only: it does not adjudicate the miss-rate gate, enable the browser tier, or replace provider/licence/artifact acceptance. No tests, builds, model downloads, matrix generation, reports, runtime probes, live sweeps, reindexing, deployment, or release acceptance were run; P02.S07 remains open.

## Notes

- No tests, builds, matrix generation, model downloads, generated reports, live sweeps, runtime probes, RAG reindexing, or deployment were run.
- No source file was changed in this tranche; concurrent shared-worktree changes were preserved.
- Closure requires an accepted Rung-2 artifact followed by the authorized held-out measurement and committed report.
