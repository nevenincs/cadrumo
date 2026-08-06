---
tags:
  - '#audit'
  - '#user-docs-search-consolidation'
date: '2026-08-06'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:9fdbe9d33ff8849e9071cfec9cbb5c18b81faecf707f75aa13fc630ff20835de'
related:
  - "[[2026-08-01-user-docs-search-consolidation-plan]]"
  - "[[2026-08-01-user-docs-search-consolidation-adr]]"
  - "[[2026-08-05-user-docs-search-consolidation-source-contract-reference]]"
---
# `user-docs-search-consolidation` audit: `final implementation review`

## Scope

Formal read-only final review of the current user-docs-search-consolidation execution scope against the accepted ADR, active plan, source-contract reference, deterministic casilla research, prior implementation/evaluator/legal audits, and current execution records. Discovery used the required `vaultspec-rag` CLI for vault and code searches; the rejected MCP `codebase` alias was not bypassed or reindexed. The review covered deterministic casilla projection/enrollment and the M130/casilla-15 route; legal reference/projection/injection/relevance parity; RAG laundering and the manifest boundary; the Rung-2 bridge/evaluator/browser fail-closed seam and temporary provider provenance; multilingual source parity; deployment boundaries; real-behaviour test shape; and shared-worktree ownership.

The reviewer made no source, test, generated-artifact, plan, deployment, staging, commit, or process changes. Evidence below distinguishes source/test evidence, a bounded English built-artifact capture, temporary provider evidence, and absent localized/deployment/acceptance evidence.

## Findings

### source-contract-parity | low | PASS within deterministic casilla, legal, and bounded English-artifact scope

Fresh RAG grounding and exact source reads found the validated-registry casilla projection, typed unified-record funnel, canonical `casilla_id` structured route, individual-locator fail-closed resolver, renderer-owned legal targets, dedicated `LEGAL` records, and manifest-target checks aligned with the accepted ADR and source-contract reference. The authorized marker-aware run recorded `63 passed in 180.00s (0:03:00)` across the casilla, legal, resolution, relevance, and Rung-2 source-contract selections. The reported projection census is 8,496 records: 6,359 casillas, 1,494 CLI records, 49 concepts, and 594 legal records; M130/casilla 15 resolves to its canonical record and `_generated/casillas/130.html#casilla-15`. The bounded English Pagefind capture reported 2,094 pages and 8,496 injected records. These are source/test and English built-artifact results only; they do not establish localized build or deployed-root parity.

### rung2-acceptance | high | Rung-2 diagnostic evidence misses the ratified threshold and cannot enable the browser tier

Temporary provider/model/tokenizer evidence is independently manifested, and the temporary validated bundle is reported at 2,130,942 canonical bytes with its recorded artifact hash. The independent float32/int8 comparison lost 0 of 32 top-five records, but the diagnostic replay under the explicit policy `minimum_coverage_ratio=0.8`, `cosine_floor=0.75`, `runner_up_margin=0.05`, and result cap 5 produced 17/32 semantic hits and 15/32 composed hits. Both miss rates exceed the ADR's ratified 0.10 line; the earlier 22/32 ladder metric was not reproducible from the available capture/bundle pair. No committed matrix/bundle, accepted browser configuration, cross-runtime JCS-vector execution, or post-Rung-2 standing report exists. The browser remains correctly disabled and fail-closed, and P02.S04-S07, P02.S25, and P02.S26 remain open.

### sweep-verification | medium | The full sweep composition test lane timed out and remains unverified

The authorized live `vaultspec-rag` sweep completed 112 mappings across 49 concepts with 0 failed queries and 0 empty mappings. The promoted relevance bytes are byte-identical to the current repository file; independent inspection confirms 112 mappings, 169 target rows, 91 unique record ids, 112 concept targets, 57 legal targets, and zero `code:` targets. This is useful live-sweep and artifact evidence. However, the broader `test_sweep.py` selection timed out at 184 seconds while materializing the four-language CLI projection, and the successful 63-test command did not include that module or the separate resident-service test. The timeout is not green evidence, so P06.S30 remains open and the laundering/manifest composition gate is not fully closed.

### multilingual-deployment | high | Localized strict builds and live deployment acceptance are still absent

Strict user-document builds for `en`, `es`, `ca`, and `hu` stopped before the Pagefind post-build stage on the same five recorded sequence/product divergences. The bounded English Pagefind capture therefore cannot stand in for four language-root artifacts. No accepted `es`/`ca`/`hu` built-root parity or deployed-root probe is recorded, and the authorized deployment preflight failed with an expired AWS session before any mutation. P03.S08 and P04.S12-P04.S13 remain open; no claim of multilingual deployment, live language-root reachability, or published search parity is justified.

### final-closure | high | The active plan is not closure-ready despite scoped P05/P06 gates being checked

The current plan has 30 executable rows, 19 checked and 11 open: P02.S04, P02.S05, P02.S06, P02.S07, P02.S25, P02.S26, P03.S08, P04.S12, P04.S13, P06.S27, and P06.S30. The checked P05 legal and P06 casilla/source gates are supported within their recorded source/test and bounded English-artifact boundaries, but the remaining open Rung-2, sweep, multilingual, deployment, and deferred Diseno-locator contracts prevent a final campaign-complete or shipped-site verdict.

### shared-worktree-safety | low | PASS: peer work and reviewer boundaries were preserved

The review did not stage, commit, deploy, terminate processes, or alter source, tests, generated artifacts, or plans. The unrelated peer WIP in `src/cadrumo/application/aggregation/_invoice_retencion.py` remains present, and the review operated only on the requested audit record through the canonical VaultSpec edit operation.

## Recommendations

- Keep all 11 open plan rows open. Treat the 63-test run, refreshed relevance file, English Pagefind capture, and temporary Rung-2 manifests as bounded evidence rather than campaign closure.
- Reproduce the full Rung-2 ladder against one accepted bundle/configuration, execute the independent JCS vector consumers, record the held-out miss-rate and locale/kind regression result, and commit the artifact/report only if the ADR thresholds pass.
- Rerun the timed-out sweep composition lane with an explicit bounded proof and retain any timeout or partial collection as unverified.
- Resolve the five strict locale-build divergences, produce each root's own Pagefind artifact, reauthenticate AWS, and then perform the required deployed-root and live-search checks.
- Keep the Diseno locator step fail-closed until official revision-aware locator evidence exists, and preserve unrelated shared-worktree WIP during follow-up work.
