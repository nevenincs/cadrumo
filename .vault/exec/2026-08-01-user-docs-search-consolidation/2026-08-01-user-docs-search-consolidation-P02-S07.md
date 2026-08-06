---
tags:
  - '#exec'
  - '#user-docs-search-consolidation'
date: '2026-08-05'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:35547909f3afebf89492e0a69ab6a32ba79ca74d7d5b1de2500d6c21d00480e6'
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

### 2026-08-05 LUNA Extra High evaluator review

Read-only LUNA Extra High review, grounded with vaultspec-rag and exact current source, found three open evaluator defects in the peer WIP: abstention statuses can carry candidates into composition (HIGH), evaluation rows/aggregates do not enforce hit/reason/matched-id arithmetic (MEDIUM), and lexical composition ties do not apply the required UTF-8 record-id fallback (LOW). The peer-owned `_rung2_evaluation.py` was not edited. P02.S07 remains open; no acceptance or measurement evidence is claimed.

### 2026-08-06 authorized measurement continuation

The provider-backed temporary bundle parses and the independent float32/int8 top-five comparison remains clean: 0 of 32 queries lost a top-five record, with maximum observed cosine drift approximately 0.002751. A diagnostic replay of the captured Pagefind observations under the explicit test policy `minimum_coverage_ratio=0.8`, `cosine_floor=0.75`, `runner_up_margin=0.05`, and result cap 5 produced 17/32 semantic hits and 15/32 composed hits; neither meets the ADR threshold of 0.10 miss-rate. The earlier supplied 22/32 ladder metric was not reproducible from the available capture/bundle pair, so no acceptance claim is made.

The Rung-2 browser config remains disabled/fail-closed. P02.S07 stays open pending an accepted config/policy, reproducible full-ladder evidence, locale/kind parity, and the held-out gate.

### 2026-08-06 RAG-grounded acceptance disposition

Fresh resident `vaultspec-rag` searches over the accepted consolidation ADR and the current compiler/evaluator/acceptance seams reconfirmed the binding boundary: R5 permits only bounded term-level semantics over the closed project vocabulary; R8/R9 require the shared tokenizer contract and measured minimum coverage; R10 requires evidence-derived cosine/margin/coverage thresholds, quantization top-five parity, locale/record-kind parity, and a held-out miss rate at or below 0.10 before browser enablement. The current report's 0.8 coverage floor, 0.75 cosine floor, and 0.05 runner-up margin are explicitly recorded measurement-policy inputs, not release authorization.

The 14 semantic misses are distributed between `no-cosine-match` and `insufficient-coverage`; they are therefore not evidence that the evaluator may admit arbitrary out-of-vocabulary held-out phrases. Adding those phrases to the matrix or lowering the ratified coverage/recall bar would invalidate the held-out measurement and contradict the accepted source contract. No code-side remediation is justified by this replay. P02.S04-P02.S07 remain open and fail-closed pending a reproducible accepted artifact/policy or new authorized evidence; the browser config remains disabled and no deployment is claimed.

### 2026-08-06 diagnostic threshold sweep

A coarse read-only calibration sweep over the reproducible bundle varied the explicit coverage floor and cosine floor without changing source or release data. With the deliberately weak `minimum_coverage_ratio=0.4`, `runner_up_margin=0.0`, and result cap 5, floors 0.0, 0.3, and 0.5 each reached only 28/32 held-out hits (0.125 miss rate); floor 0.7 fell to 26/32 (0.1875). This is diagnostic, not threshold acceptance: it does not supply an independent calibration corpus, does not authorize lowering the contract, and still remains above the ratified 0.10 ceiling. The previously recorded policy replay remains the standing report.

### 2026-08-06 browser seam continuation

Fresh `vaultspec-rag` searches and the accepted Sol-medium architecture disposition confirm that the Rung-2 representations and D8 band-first ladder remain unchanged. The real Pagefind capture found the installed result API exposes an ephemeral `id` plus `data()`, with the destination URL in `data.url`; the controller's prior `result.url` relevance join was therefore invalid. The LUNA MAX repair carries the Pagefind id through the two-pass join, retains `data.url` for destination/dedupe, and does not promote direct model identity across the accepted legal DOC band.

Focused real verification passed: `uv run --no-sync pytest -q dev/docs/terminology/tests/test_rung2_evaluation.py` returned `10 passed in 9.57s`; `uv run --no-sync pytest -q -m integration dev/docs/tests/test_search_page_inline_ladder.py dev/docs/tests/test_palette_ranking.py` returned `3 passed in 43.86s`; `node --check docs/_static/cadrumo-docs.js` and scoped `git diff --check` passed. The full local Pagefind build and 32-query browser capture are recorded in P02.S31. The miss-rate/acceptance evidence remains rejected; no browser enablement, artifact promotion, commit, push, or deployment occurred.

### 2026-08-06 provider-parity remeasurement (diagnostic only)

The LUNA MAX representation-parity correction in `_model2vec_provider.py` was measured against the real pinned `model2vec==0.8.2` provider and the current authoritative inputs. The fresh temporary bundle contained 8,498 records, 112 queries, and 152 query tokens; it measured 22/32 semantic hits (miss rate `0.3125`) and aggregate coverage 92/123 (`0.7479674796747967`). This is an improvement over the prior diagnostic 18/32 semantic result, but it remains above the ratified `0.10` miss-rate ceiling and below the `0.8` coverage policy floor. The ten remaining rows are coverage failures, not cosine-floor failures.

This measurement does not replace `rung2-report.json`, does not claim a full-ladder replay, locale/kind parity, browser acceptance, artifact promotion, or enablement, and does not close P02.S04-P02.S07. The accepted Update 11 authority remains zero-entry and held-out queries remain evaluation-only; no held-out phrase, threshold relaxation, or synthetic alias was introduced. Deployment was not performed.

### 2026-08-06 SOL-high architecture disposition and closed-vocabulary failure classification

A one-time SOL-high architecture adjudication, grounded in the accepted Rung-2 ADR/Update 11 and the prior successful vaultspec-rag semantic grounding, confirms that the current representation, normalization, query-token coverage contract, thresholds, bridge, and runtime boundary must not be changed under the existing ADR. Fresh semantic retrieval is currently unavailable: the managed vaultspec-rag service reports a stalled code-index job, GPU capacity exhaustion, and an incomplete local code collection; the fallback search explicitly warns that absence is not evidence. Exact RAG source-file retrieval and the prior resident semantic results remain the grounding used for this disposition.

The current pinned-provider diagnostic remains 22/32 semantic hits (miss rate 0.3125), 92/123 covered query tokens (0.7479674796747967), and ten below the 0.8 coverage floor; quantization top-five loss is 0/32. The held-out corpus remains evaluation-only. No held-out query or token was added to the authority, no threshold was lowered, and no browser configuration was enabled.

Read-only classification of the ten below-floor queries found no current Handbook/relevance query-token identity that the assembler failed to enroll, so no category-3 implementation divergence is evidenced. The missing surfaces fall into two bounded groups: query scaffolding/function words (cuando, presento, que, es, para, mis, como, funciona, a, este, dar, alta, un, sin) that the closed vocabulary is not required to admit; and domain words (autonomos, trabajadores, oficina, pagar, factura, luz, deducible, autonomo, hacienda, vender, francia, libro, ingresos, gastos) that could be candidates only after independent, non-held-out ratification. The existing synonym queue confirms that deducible is rejected as too broad/tax-directional and pro-rata remains proposed; neither is admissible authority. The committed authority therefore correctly remains zero-entry.

The four-locale committed relevance surface was checked without changing it: ES has 91 mappings over 49 concepts, EN 17 over 15 concepts, CA 1 over 1 concept, and HU 3 over 3 concepts. This is source-side locale evidence only; it is not a substitute for the outstanding built/deployed per-root parity gates.

The SOL disposition is to close none of P02.S04-P02.S07. The minimum safe continuation is to obtain independent RAG-grounded ratification evidence for any domain alias candidate, or obtain a separately approved ADR amendment before changing representation/coverage semantics, then recompile the same accepted matrix and rerun the existing gates. No source correction is justified by this failure classification. Deployment is also not evidenced: the current AWS session is expired and the accepted Rung-2/build gates are not green.

## Notes

- No tests, builds, matrix generation, model downloads, generated reports, live sweeps, runtime probes, RAG reindexing, or deployment were run.
- No source file was changed in this tranche; concurrent shared-worktree changes were preserved.
- Closure requires an accepted Rung-2 artifact followed by the authorized held-out measurement and committed report.

### 2026-08-05 source continuation: full-ladder held-out observation seam

Fresh vaultspec-rag grounding over the accepted ADR, the P02.S07 audit, the source-contract reference, the browser semantic seam, and the current evaluator confirmed that the missing source boundary was a pure full-ladder evaluator over independently supplied lexical observations. The source now adds `Rung2LadderObservation` and `evaluate_rung2_ladder` in `dev/docs/terminology/_rung2_evaluation.py`. The seam requires one validated observation per held-out query in canonical corpus order, rejects duplicate/missing/unexpected observations, composes the existing semantic result with the supplied lexical rows, and evaluates the explicit five-result cap.

This is source-only measurement plumbing. It performs no Pagefind access, artifact I/O, report generation, float32-versus-int8 comparison, acceptance adjudication, or release decision. P02.S07 remains open until an accepted Rung-2 bundle/config, independent Pagefind observations, float32-versus-int8 evidence, and the authorized standing report exist.

Static local review and `git diff --check` found no issue. The requested LUNA Max implementation and LUNA Extra High review dispatches timed out and were shut down without returning a review; no LUNA approval is claimed. No tests, builds, model downloads, matrix/report generation, runtime probes, live sweeps, reindexing, deployment, or artifact acceptance were run.

### 2026-08-05 static verification continuation

The exclusive source file now passes targeted `uv run --no-sync ruff check dev/docs/terminology/_rung2_evaluation.py` and `uv run --no-sync basedpyright dev/docs/terminology/_rung2_evaluation.py`, as well as AST parsing and `git diff --check`. These are static checks only. Tests, builds, model downloads, matrix/report generation, Pagefind/runtime probes, live sweeps, reindexing, deployment, and artifact acceptance remain deferred; P02.S07 remains open.

### 2026-08-05 source continuation: independent top-five-loss comparison seam

Fresh vaultspec-rag grounding over the P02.S07 audit, the accepted Rung-2 source contract, and the current static-matrix observation types confirmed that the remaining comparison boundary can be represented without inventing a model or artifact. The source now adds `Rung2TopFiveObservation`, `Rung2TopFiveLossRow`, `Rung2TopFiveLossEvidence`, and `compare_rung2_top_five` in `dev/docs/terminology/_rung2_evaluation.py`. The pure seam requires independently supplied float32 and int8 ranked record-id tuples, validates held-out corpus alignment and duplicate-free top-five lists, and derives per-query membership loss plus aggregate query loss rate.

This is not a float32 or int8 scorer and does not establish that either capture was produced from an accepted configuration. It performs no model loading, vector scoring, artifact I/O, report generation, acceptance adjudication, or release decision. P02.S07 remains open until real accepted configurations produce the observations and the authorized standing report is committed.

Targeted Ruff, basedpyright, AST parsing, and diff checks pass. No tests, builds, model downloads, matrix/report generation, Pagefind/runtime probes, live sweeps, reindexing, deployment, or artifact acceptance were run.

### 2026-08-05 source correction: direct top-five loss-row validation

A fresh vaultspec-rag review of the new comparison seam found that the aggregate constructor was strict, but a caller could instantiate `Rung2TopFiveLossRow` directly with duplicate ranked ids. The row validator now rejects duplicate float32 or int8 ids as well as the observation wrapper, preserving fail-closed ranking evidence at every model boundary.

Targeted Ruff, basedpyright, and diff checks pass. This remains source-only; no tests, measurements, artifacts, runtime probes, or acceptance were run.

### 2026-08-06 authorized standing report

Fresh vaultspec-rag grounding of the report boundary (CLI request e37945e2b1874e178bafb76e6b3029fe) confirmed that the source evaluator remains measurement-only and that acceptance belongs to the existing fail-closed browser-config contract. The new strict report contract is dev/docs/terminology/_rung2_report.py, with real-behaviour coverage in dev/docs/terminology/tests/test_rung2_report.py; the materialized evidence is src/cadrumo/_data/terminology/evaluation/rung2-report.json.

The current route-refresh bundle and independent replay produced 32 semantic cases with 18 hits / 14 misses (0.4375 miss-rate) and 32 composed full-ladder cases with 15 hits / 17 misses (0.53125 miss-rate), under the explicit policy minimum_coverage_ratio=0.8, cosine_floor=0.75, runner_up_margin=0.05, and result cap 5. Aggregate coverage was 92 of 123 query tokens (0.7479674796747967), with 20 fully covered queries, 0 zero-covered queries, and 10 below the policy minimum. Independent float32/int8 replay lost 0 of 32 top-five memberships; maximum observed cosine drift was 0.002234607622454972.

The report records the pre-Rung-2 baseline beside the current diagnostic measurement: 32 cases / 26 hits / 6 misses / 0.1875 before Rung 2, and an explicit rejected decision with browser configuration disabled. It is not a post-Rung-2 acceptance baseline: both semantic and full-ladder recall miss the ratified 0.10 threshold, coverage is below policy, acceptance evidence was not supplied, and four-root locale/kind parity for the Rung-2 artifact remains unproven. P02.S07 remains open; no acceptance or deployment claim is made.

Focused verification passed: uv run --no-sync pytest -q dev/docs/terminology/tests/test_rung2_report.py dev/docs/terminology/tests/test_rung2_evaluation.py returned 13 passed in 4.31s; scoped Ruff, basedpyright, and git diff --check passed.
