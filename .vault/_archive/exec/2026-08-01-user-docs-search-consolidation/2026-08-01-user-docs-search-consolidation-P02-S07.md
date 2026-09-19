---
tags:
  - '#exec'
  - '#user-docs-search-consolidation'
date: '2026-08-05'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:145e8a215cb96f6ea2f64c44bd1840ca06c491ff408402d9ff18ce567a1e1018'
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

### 2026-08-06 LUNA MAX authorized provider continuation

Fresh vaultspec-rag grounding and a local pinned-provider run completed without source edits. The local dev environment used model2vec==0.8.2 and the immutable Potion revision e7421cd79c75fc506b88bb75723ae0a234994720; raw provider/model/tokenizer manifests were verified before provider import. The temporary bundle contained 112 queries, 152 query tokens, and 8,505 records; matrix size was 254,588 bytes and bundle size was 2,135,413 bytes with raw SHA-256 b3902f8a0f90b19eac82a75051a0d5c57485797fde9d96d3a820f36a4401335f. It was not promoted, committed, or enabled.

Focused contract verification returned 67 passed; real Pagefind/controller integration returned 4 passed; Ruff, basedpyright, Node syntax, and scoped diff checks passed. The semantic replay was 22/32 hits (miss rate 0.3125) with 92/123 query-token coverage (0.7479674796747967), including 10 below the 0.8 floor. The captured full ladder remains 15/32 (miss rate 0.53125). P02.S04-P02.S07, P02.S31, and P02.S32 remain open; browser configuration stays disabled and deployment was not attempted.

### 2026-08-06 LUNA EXTRA HIGH semantic-result invariant hardening

Fresh vaultspec-rag grounding over the browser-equivalent evaluator and accepted Rung-2 ordering contract identified a concrete fail-closed gap: semantic result models did not enforce the aggregate coverage bound, unique record ids, deterministic score/weight/UTF-8 ordering, or the fixed five-result cap. The LUNA EXTRA HIGH worker corrected only `dev/docs/terminology/_rung2_evaluation.py`; `_rung2_acceptance.py` was reviewed and unchanged.

The worker reported focused Rung-2 verification at `40 passed`, Ruff clean, basedpyright clean (`0 errors, 0 warnings, 0 notes`), scoped diff-check clean, and direct rejection probes for six candidates and invalid ordering/coverage. No held-out report or accepted artifact was produced.

P02.S07 remains open. The standing provider-backed replay remains rejected at 22/32 semantic hits (`0.3125` miss rate), 15/32 composed hits, and 92/123 aggregate token coverage (`0.7479674796747967`); the browser configuration stays disabled and fail-closed.

### 2026-08-06 current compile does not change the acceptance verdict

The same fresh `vaultspec-rag`-grounded provider compile passed the bridge after the bounded cross-axis weight correction, but it is build evidence only. It does not rerun or improve held-out semantic/composed-ladder metrics, quantization-drift measurement, or the browser/licence gate. The current standing evidence therefore remains the previously recorded rejected Rung-2 result; the temporary bundle was not promoted or enabled. P02.S07 remains open.

### 2026-08-06 current browser ladder does not clear the acceptance gate

The independent Playwright/Pagefind capture recorded in P02.S31 was replayed against the current temporary pinned-provider bundle. The full composed ladder reached `16/32` held-out hits and `16/32` misses (`0.5000` miss-rate). The semantic-only replay of that same bundle reached `22/32` (`0.3125` miss-rate); aggregate token coverage remained `92/123 = 0.7479674796747967`, with 20 fully covered cases, 10 below the `0.8` minimum, and 0 zero-covered cases.

This current measurement is useful evidence that the bridge correction and provider compile are operational, but it is not a new standing acceptance report. The local Pagefind build is not hash-linked to a promoted bundle, and quantization/top-five loss, licence provenance/size, and four-locale/per-kind parity evidence are not all accepted. The composed miss-rate remains above the ratified `0.10` bar. The committed report was therefore intentionally not overwritten, the temporary bundle was not promoted or enabled, and P02.S07 remains open.

### 2026-08-07 authoritative full-bundle semantic remeasurement

The authoritative input assembler now succeeds, so the fresh full bundle—not the earlier manifest-reuse diagnostic—was loaded through `load_rung2_search_bundle` and replayed under the ratified policy. It contains 8,505 manifest records and 2,138,574 canonical bytes. Semantic replay produced 22/32 hits and 10/32 misses (`0.3125` miss rate); coverage was 93/123 tokens (`0.7560975609756098`), with 20 fully covered queries, 10 below the 0.8 minimum, and 0 zero-covered queries. All ten semantic misses abstained as `insufficient-coverage`.

The previous independently captured Pagefind observations are not persisted outside the local build tree; therefore the prior 16/32 composed-ladder result remains diagnostic evidence against its earlier temporary bundle and is not silently relabeled as a fresh full-bundle ladder report. No new lexical observations were fabricated. The standing report remains rejected/disabled, P02.S07 remains open, and no browser enablement, artifact promotion, commit, push, or deployment occurred.

### 2026-08-06 alias remeasurement remains diagnostic

Following fresh `vaultspec-rag` grounding and the live `ServiceRagSearchClient` alias sweep, the independent authority admits only Spanish `autonomos` -> `modelo 130`. Recompiling from the current relevance and authority inputs produced 113 vocabulary queries, 153 query tokens, and 113 mappings with zero failures; the bundle is 2,137,428 bytes.

The held-out evaluator remains unchanged at 22/32 hits and a 0.3125 miss rate. The new alias improves the `modelo 130 para autonomos` case from 2/4 to 3/4 tokens, but the case still misses `para`; the acceptance threshold is therefore not met. The measurement is recorded as a diagnostic result only, with no held-out-term promotion, threshold relaxation, or baseline replacement. P02.S07 remains open pending a valid Rung-2/browser composed-ladder measurement and standing-baseline decision.

### 2026-08-06 current alias bundle replay detail

A direct source-only replay of the current temporary alias bundle through `evaluate_rung2_held_out` produced 22/32 semantic hits, 10 misses, and a 0.3125 miss rate. The bound coverage evidence is 93/123 query tokens (`0.7560975609756098`), with 20 fully covered queries, 0 zero-covered queries, and 10 below the 0.8 minimum. The query-set version remains 1 and the bundle artifact SHA-256 is `ed69c3b6a6d9f92e77ad25cd5aaf9fd76694f3e5daa57369251a21302e14778f`. This is a reproducible diagnostic replay, not a new standing report: the composed Pagefind ladder for this exact bundle, independent float32/int8 loss evidence, and accepted locale/kind parity are not all hash-linked and accepted.

A fresh exact-bundle semantic rerun after the focused contract suite confirms query-set version `1`, 22/32 hits, 10/32 misses (`0.3125`), and coverage `93/123 = 0.7560975609756098`; all ten misses abstain as `insufficient-coverage`. The previous `rung2-report.json` was intentionally left unchanged because its lexical observations belong to an earlier artifact and no fresh Pagefind observation file exists for this exact bundle. Mixing those measurements would create a false baseline. P02.S07 remains open.

### 2026-08-07 current-head authoritative semantic replay

After the current-head compiler completed, the fresh full bundle was loaded through `load_rung2_search_bundle` and evaluated against query-set version 1 with the explicit policy `minimum_coverage_ratio=0.8`, `cosine_floor=0.75`, `runner_up_margin=0.05`, and result cap 5. The diagnostic bundle contains 8,516 manifest records, 114 matrix rows/terms, 2,141,633 bytes, and artifact SHA-256 `7907fd6ad903dcb1189286b181639c5e816b061adc4e697497e489f32c6f254d`. Replay produced 22/32 semantic hits and 10/32 misses (`0.3125` miss rate), with 93/123 covered query tokens (`0.7560975609756098`), 22 fully covered rows, 10 below the 0.8 floor, and 0 zero-covered rows. All ten misses abstained as `insufficient-coverage`: `cuando presento el modelo 303`, `que es la prorrata especial`, `modelo 130 para autonomos`, `resumen anual de retenciones de mis trabajadores`, `como funciona la ventanilla unica de iva`, `impuesto de sociedades a pagar este ano`, `factura de la luz deducible`, `dar de alta un autonomo en hacienda`, `vender a francia sin iva`, and `libro de ingresos y gastos`.

This is reproducible diagnostic evidence that the current compiler/provider seam operates; it does not satisfy the ratified 0.10 miss-rate or 0.8 coverage gates, and it is not a new standing report. The bundle was not promoted, the browser tier remains disabled/fail-closed, and no locale parity, full-ladder Pagefind capture, or deployment claim is made. P02.S07 remains open.

### 2026-08-07 current HEAD semantic replay confirmation

The exact bundle compiled from `HEAD 9e6e552fee` was reloaded and replayed under the existing explicit policy. It remains 22/32 hits, 10/32 misses, and `0.3125` miss rate, with 93/123 covered query tokens (`0.7560975609756098`), 22 fully covered rows, 10 below the 0.8 floor, and 0 zero-covered rows. Every miss remains `insufficient-coverage`. This is diagnostic evidence only: the 0.10 miss-rate gate is not met, no full-ladder observation is hash-linked to this bundle, the browser tier remains disabled, and P02.S07 remains open.

### 2026-08-07 pushed HEAD d24ae2fdee semantic replay

The exact diagnostic bundle compiled from pushed `HEAD d24ae2fdee` was reloaded under the existing explicit policy. It produced 22/32 hits, 10/32 misses, and `0.3125` miss rate, with 93/123 covered query tokens (`0.7560975609756098`), 22 fully covered rows, 10 below the 0.8 floor, and 0 zero-covered rows; all misses were `insufficient-coverage`. This confirms the semantic result is unchanged at the pushed HEAD, but it remains above the ratified 0.10 gate and has no hash-linked current full-ladder Pagefind capture. The browser tier remains disabled and P02.S07 remains open.

### 2026-08-11 retirement under ADR Update 12

This row is retired, not delivered. No post-Rung-2 baseline will be measured because no post-Rung-2 ladder exists.

The 0.1875 pre-Rung-2 held-out miss rate therefore stands as the project's standing and final honest recall statement, not as a baseline awaiting improvement. The measurement seam this record established, the held-out corpus, the evaluator and the report command, survives and continues to measure the lexical ladder.

The measured prose-recall gap is not carried forward to a semantic tier. The dominant cause is Pagefind term conjunction rather than semantics: dropping function words alone lifted one probe from 2 results to 36 and another from 2 to 41, and a corpus-frequency heuristic was tested and shown unable to separate the classes in this corpus. That is lexical-tier work under an explicit per-language function-word authority or progressive term relaxation.

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
