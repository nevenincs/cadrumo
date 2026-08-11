---
tags:
  - '#exec'
  - '#user-docs-search-consolidation'
date: '2026-08-06'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:1d4584c95fb71650bdacc19735a1788a9f639641820972211945cadd4787e342'
step_id: 'S32'
related:
  - "[[2026-08-01-user-docs-search-consolidation-plan]]"
---

# Introduce an independent versioned query and alias authority from RAG-grounded project vocabulary, bind its provenance into Rung-2 inputs, and recompile and remeasure without using held-out terms

## Scope

- `src/cadrumo/_data/terminology/` and `dev/docs/terminology/`

## Description

Implement the ADR Update 11 authority as a strict build-time input. Keep the Handbook and the synonym queue in their existing roles, independently sweep any ratified aliases through vaultspec-rag, bind raw-byte authority identity into Rung-2 provenance, and refuse held-out leakage or parity drift.

## Tracking

- [x] Add the versioned authority schema, committed data contract, deterministic ordering, and anchoring validation.
- [x] Extend sweep and Rung-2 input assembly to consume the authority as an independent union.
- [x] Bind authority path, schema version, authority version, and raw-byte digest into immutable provenance and downstream contracts.
- [x] Add real-behaviour tests for malformed, stale, colliding, unratified, non-canonical, held-out, and parity-drift inputs.
- [x] Run the live vaultspec-rag refresh with the authority loaded and retain its result as evidence.
- [ ] Recompile and accept a Rung-2 matrix, then measure an enabled ladder without using held-out terms.

## Outcome

Implemented the independent, versioned, build-time query/alias authority and bound its raw-byte identity into Rung-2 input provenance. The committed authority intentionally contains zero entries because no additional alias had an independent ratification evidence chain; no held-out term was copied or admitted. The live RAG refresh remained 112 queries, 49 concepts, and 0 failed, so the existing committed relevance baseline remains authoritative. S32 stays open: no Rung-2 matrix was generated, enabled, accepted, or deployed.

## Verification

```
uv run --no-sync pytest -q dev/docs/terminology/tests/test_rung2_query_authority.py dev/docs/terminology/tests/test_rung2_inputs.py dev/docs/terminology/tests/test_rung2_provenance.py dev/docs/terminology/tests/test_rung2_acceptance.py dev/docs/terminology/tests/test_sweep.py
55 passed in 46.29s

uv run --no-sync pytest -q dev/docs/terminology/tests/test_rung2_acceptance.py dev/docs/terminology/tests/test_rung2_evaluation.py dev/docs/terminology/tests/test_rung2_report.py dev/docs/terminology/tests/test_rung2_provenance.py dev/docs/terminology/tests/test_rung2_inputs.py dev/docs/terminology/tests/test_rung2_query_authority.py
61 passed in 4.59s

uv run --no-sync python -c "from dev.docs.terminology._rung2_inputs import build_rung2_compilation_inputs; x=build_rung2_compilation_inputs(); print({'queries': x.sweep.query_count, 'vocabulary': len(x.vocabulary), 'tokens': len(x.query_tokens), 'records': len(x.records), 'authority_version': x.query_alias_authority.authority_version, 'authority_entries': len(x.query_alias_authority.entries), 'alias_source': x.provenance.query_alias_authority.source_relpath})"
{'queries': 112, 'vocabulary': 112, 'tokens': 152, 'records': 8498, 'authority_version': 1, 'authority_entries': 0, 'alias_source': 'src/cadrumo/_data/terminology/rung2/query-alias-authority.json'}

uv run --no-sync python -c "from dev.docs.terminology._miss_rate import evaluate_held_out_miss_rate; x=evaluate_held_out_miss_rate(); print({'case_count': x.case_count, 'hit_count': x.hit_count, 'miss_count': x.miss_count, 'miss_rate': x.miss_rate, 'compiled_query_count': x.compiled_query_count})"
{'case_count': 32, 'hit_count': 26, 'miss_count': 6, 'miss_rate': 0.1875, 'compiled_query_count': 112}

uv run --no-sync python -c "from dev.docs.terminology._sweep import ServiceRagSearchClient, run_sweep; x=run_sweep(client=ServiceRagSearchClient(timeout_s=60.0), reindex=True, port=8766); print({'query_count': x.query_count, 'concept_count': x.concept_count, 'failed_query_count': x.failed_query_count, 'targeted_queries': sum(bool(mapping.targets) for mapping in x.mappings), 'reindex_note': x.reindex_note})"
{'query_count': 112, 'concept_count': 49, 'failed_query_count': 0, 'targeted_queries': 112, 'reindex_note': 'reindex queued/accepted: Source code re-index job queued on service: 783df457-f3cf-4f3e-96ba-3d898394bdfb'}

uv run --no-sync ruff check dev/docs/terminology/_rung2_query_authority.py dev/docs/terminology/_rung2_provenance.py dev/docs/terminology/_rung2_inputs.py dev/docs/terminology/_sweep.py dev/docs/terminology/__init__.py dev/docs/terminology/tests/test_rung2_query_authority.py dev/docs/terminology/tests/test_rung2_inputs.py dev/docs/terminology/tests/test_rung2_provenance.py dev/docs/terminology/tests/test_rung2_acceptance.py dev/docs/terminology/tests/test_sweep.py
All checks passed!

uv run --no-sync basedpyright dev/docs/terminology/_rung2_query_authority.py dev/docs/terminology/_rung2_provenance.py dev/docs/terminology/_rung2_inputs.py dev/docs/terminology/_sweep.py dev/docs/terminology/__init__.py dev/docs/terminology/tests/test_rung2_query_authority.py dev/docs/terminology/tests/test_rung2_inputs.py dev/docs/terminology/tests/test_rung2_provenance.py
0 errors, 0 warnings, 0 notes

git diff --check -- dev/docs/terminology/_rung2_query_authority.py dev/docs/terminology/_rung2_provenance.py dev/docs/terminology/_rung2_inputs.py dev/docs/terminology/_sweep.py dev/docs/terminology/__init__.py dev/docs/terminology/tests/test_rung2_query_authority.py dev/docs/terminology/tests/test_rung2_inputs.py dev/docs/terminology/tests/test_rung2_provenance.py dev/docs/terminology/tests/test_rung2_acceptance.py dev/docs/terminology/tests/test_sweep.py src/cadrumo/_data/terminology/rung2/query-alias-authority.json
exit 0
```

## Notes

- Fresh vaultspec-rag grounding was performed against the accepted Rung-2 ADR, the Rung-2 research, the current Handbook enumeration, the relevance assembler, and the held-out boundary.
- The current authority design is build-time only; it does not add runtime RAG, model downloads, or a new search server.

- Fresh vaultspec-rag grounding used the accepted Update 11 ADR and the code seams in `_rung2_inputs.py`, `_rung2_provenance.py`, `_sweep.py`, and the new authority module before implementation.
- The reindex request was accepted by the resident service; no relevance JSON, matrix, browser bundle, or deployment artifact was written by this execution.
- LUNA MAX and LUNA EXTRA HIGH coding slots were delegated with exclusive scopes but returned no patch before their inactive slots were closed; the parent completed the same bounded implementation locally without touching their absent scopes.

### 2026-08-06 follow-up review hardening

The raw-byte provenance helper now reloads the committed authority and rejects a mismatched supplied model; the added tamper test passes. The complete Rung-2 contract selection was rerun as `62 passed in 8.67s`; ruff, basedpyright, node syntax, and the isolated browser gate remain clean. P02.S33 carries the browser-validator correction found during review.

### 2026-08-06 LUNA MAX continuation

The independent query/alias authority was revalidated at schema/authority version 1 with zero aliases, 112 admitted queries, and zero held-out overlap. Fresh RAG-grounded discovery found no independently ratified alias admissible under the current Handbook contract, so no alias was invented to improve the rejected measurement. P02.S32 remains open for accepted remeasurement evidence; no source or data change was made.

### 2026-08-06 current provider compile provenance and held-out separation

The current pinned-provider temporary bundle was assembled through the independent authority path. The committed authority is schema `cadrumo.docs-search.rung2-query-aliases.v1`, version `1`, with zero alias entries; the 32-case held-out corpus has zero alias overlap. The bundle records the authority source digest `0b75e8bb03129e6ec1ec74093bda7fcecbbf2d2180159c4c14964a47bf7b0d5e`, the committed relevance source digest `4e686b6b4dda2c525358e5b02213f9664683c032dfc9c809da54b5f844377226`, schema `3`, and serialized size `2,135,413` bytes.

This proves provenance binding and independent held-out separation for the current diagnostic compile; it does not prove relevance acceptance. The browser replay remains `16/32` composed hits (`0.5000` miss-rate) and the semantic-only replay remains `22/32` (`0.3125`), so no alias authority rows are being invented from held-out failures and P02.S32 remains open pending independently ratified vocabulary/relevance and an accepted remeasurement.

### 2026-08-06 ratified alias and scoped-sweep continuation

Fresh `vaultspec-rag` grounding ranked the independent query/alias authority, the Handbook vocabulary enumerator, and the sweep laundering path as the governing implementation seam. A real `ServiceRagSearchClient` run against the live service on port 8766 was then restricted to `modelo-130` with an explicit temporary authority and `reindex=False`: `autonomos`, `modelo 130`, and `pago fraccionado` each resolved to `concept:modelo-130`; the three-query sweep reported zero failures.

The first independently ratified closed-vocabulary entry is now committed in `src/cadrumo/_data/terminology/rung2/query-alias-authority.json`: Spanish `autonomos` maps canonically to `modelo 130`, with the review reason and date preserved. The laundered relevance artifact now contains 113 queries, 49 concepts, and zero failed queries; the new alias is a concept record targeting `_generated/glossary.html#term-modelo-130`.

The scoped sweep path in `dev/docs/terminology/_sweep.py` now accepts an explicit authority and validates only authority entries belonging to a requested concept subset before selecting them. This preserves fail-closed validation while allowing a one-concept diagnostic sweep after a global alias has been ratified. The focused real-behaviour suite covering inputs, authority, relevance data, and sweep behavior is green at 39 passed; Ruff, basedpyright, and the browser JavaScript syntax check are also green.

The step remains open. The diagnostic Rung-2 compile with this authority contains 113 vocabulary queries, 153 query tokens, 113 mappings, zero failed queries, and a 2,137,428-byte bundle. The held-out evaluator remains 22/32 hits with a 0.3125 miss rate, and `modelo 130 para autonomos` reaches only 3/4 coverage because `para` is not admitted. No threshold, held-out query, or broad semantic alias was changed to force acceptance.

### 2026-08-07 RAG-grounded candidate review

Supported `vaultspec-rag` JSON searches were rerun against the current target root before considering further authority changes. The service returned a consistent combined index for the worktree (`108,474` indexed items; code generation `d84b4cc5a77d414f97b0d58b7dc240ea`). The `autonomos` query ranked the existing alias-scope audit, the `modelo-130` Handbook fragment, the alias-authority tests, and the Modelo 130 rule-delta reference; the existing Spanish alias is therefore retained. Searches for `deducible`/electricity expenses/bookkeeping and for France/IVA intra-community sales returned broad legal/manual corpus hits rather than a unique approved Handbook concept-plus-canonical-query mapping. No additional alias was admitted. The human-readable RAG renderer still fails on indexed PDF results with a UTF-8 decode error; JSON mode was used to preserve the service result without that renderer failure. P02.S32 remains open pending an accepted remeasurement, not broader alias invention.

### 2026-08-07 candidate alias authority remeasurement

Fresh vaultspec-rag searches were followed by a scoped live `ServiceRagSearchClient` sweep over three independently worded candidate queries and their approved Handbook concepts: nine queries, three concepts, and zero retrieval failures. `alta censal` resolved to `legal:orden-eha-1274-2007:art-1`, `legal:orden-eha-1274-2007:art-2`, and `concept:modelo-036`; `resumen anual retenciones trabajadores` resolved to `legal:orden-eha-3127-2009:art-1` and `concept:modelo-190`. Neither is a safe one-to-one concept alias. `retencion alquiler oficina` resolved only to `concept:modelo-115`, but it is materially a paraphrase of an existing held-out case and was rejected to preserve held-out separation.

The same RAG searches returned broad manual/legal guidance rather than a unique Handbook concept for bookkeeping and for a generic quarterly-IVA wording. No alias-authority row or relevance mapping was changed; P02.S32 remains open for accepted remeasurement rather than vocabulary leakage.

### 2026-08-08 post-commit authority/input verification

The RAG-ratified authority and relevance expansion, together with the provider/tokenizer provenance gate, were promoted in isolated commit `c918425f56` and pushed to `origin/main`; the unrelated staged peer payload was not included. The bounded post-commit suite returned `48 passed in 4.75s`, Ruff passed, and basedpyright reported `0 errors, 0 warnings, 0 notes` for the acceptance/input/authority modules.

The current authoritative assembler now succeeds from the committed inputs with 114 queries/vocabulary rows, 153 query tokens, 8,516 projected records, authority version 1 with two entries, and zero failed queries. The held-out boundary remains unchanged and no held-out term supplied an authority row. The final checklist item remains open because the current Rung-2 diagnostic measurement is not accepted: semantic replay is 22/32 hits with `0.3125` miss-rate and `0.7561` coverage, so no browser configuration is enabled.

### 2026-08-11 close under ADR Update 12

This row closes delivered-narrower, and the narrowing is stated rather than absorbed.

Delivered: the independent, versioned, build-time query/alias authority exists, is strictly loaded and schema-validated, enforces canonical ordering and duplicate refusal, is anchored to a repository-relative path with a raw-byte digest, and is consumed by the live sweep and the sweep command. It now carries two independently ratified entries, so this record's earlier statement that it ships with zero entries is superseded by the tree.

Retired: binding its provenance into Rung-2 compilation inputs, recompiling, and remeasuring. All three presuppose the Rung-2 artefact that ADR Update 12 (D12) rules will not be produced.

Re-homed: under D13 the authority's path segment and schema token no longer name the retired tier. That rename landed atomically across the committed JSON, the loader and the tests under the P02.S37 row, so nothing resolves the retired name.

What this row was originally for survives the retirement intact. The authority admits reviewed aliases into the closed query vocabulary the sweep runs, and that sweep produces the committed relevance mapping that boosts lexical results. That is rung-1 work, and rung 1 ships.

## 2026-08-06 independent alias sweep and sweep-plumbing continuation

Fresh vaultspec-rag grounding over the alias authority, `_rung2_inputs.py`, `_sweep.py`, and the ratification queue confirms that aliases remain independent ratified vocabulary and must be swept through the same live RAG resolver/wrangler boundary; held-out queries cannot supply authority entries. The sweep runner now accepts an explicit validated `query_alias_authority` and the cadence CLI exposes `--alias-authority`, while the omitted path continues to load the committed authority through the existing enumerator default. A focused recorded-service sweep regression covers enumeration, the common pipeline, and concept seeding.

The only existing strong proposed candidate, English `pro-rata` for `prorrata`, was independently swept against the resident service without adding it to authority. The current 20-hit result resolved 13 hits and, after wrangling, retained four targets: `concept:prorrata-especial` plus three `code:*` records (`cadrumo.domain.iva._prorrata`, `cadrumo.application.calculations._prorrata_regularizacion`, and `cadrumo.application.modelo._prorrata_regularizacion_advisory`); its dominant cluster was codebase (`src/cadrumo`, size 3), with six collapses and ten drops. This is not a stable one-to-one mapping to `prorrata`, so the alias remains proposed and the committed authority remains zero-entry. No held-out term, alias JSON, relevance mapping, browser configuration, or deployment surface was changed. P02.S32 remains open pending an independently RAG-grounded, unambiguous ratification and accepted remeasurement.

### 2026-08-06 explicit-authority regression verification

The explicit alias-authority seam was verified without changing the committed authority or relevance data:

- `uv run --no-sync pytest -q dev/docs/terminology/tests/test_sweep.py` returned `14 passed in 53.53s`.
- Ruff and basedpyright passed for the sweep runner, cadence CLI, and focused test.
- `uv run --no-sync python -m dev.docs.terminology.sweep --help` returned successfully and exposed `--alias-authority`.

The regression covers the same enumeration, retrieval, resolution, wrangling, laundering, and deterministic concept-seeding path used by the live runner. No Rung-2 matrix, browser configuration, relevance mapping, or deployment artifact was promoted. S32 remains open for an accepted remeasurement.

## 2026-08-07 ratified alias continuation and diagnostic remeasurement

Fresh `vaultspec-rag` grounding was repeated before recording this continuation. The supported code search (`--type code`) ranked the Rung-2 acceptance, browser bridge, input assembly, and provenance seams; the code index matched this worktree with 79,474 indexed items and a consistent integrity verdict. A combined search for `autoliquidacion iva modelo 303 canonical query alias authority` independently surfaced the accepted Modelo 303 formula ADR, the canonical `modelo-303` terminology fragment, the alias-authority regression, and the official IVA manual corpus. The MCP search wrapper still rejects the unsupported `codebase` source alias, so this evidence uses the supported CLI source types.

LUNA MAX completed the bounded authority update and LUNA EXTRA HIGH completed the bounded relevance update. The committed authority now contains two independently ratified Spanish entries: `autonomos` -> `modelo-130` and `autoliquidacion iva` -> `modelo-303`. A live `ServiceRagSearchClient` sweep on port 8766 resolved the three-query Modelo 303 diagnostic to the unique `concept:modelo-303` target with zero failed queries. The laundered relevance artifact now reports 114 queries, 49 concepts, and zero failed queries; both added rows are concept records targeting their canonical glossary anchors. No held-out query supplied either alias.

The bounded post-update contract run returned `98 passed in 110.56s`; Ruff and the scoped diff check passed, and the VaultSpec feature check remained at zero errors and zero warnings. The accepted runtime gate is not proven: the fresh Pagefind projection path could not assemble because unrelated peer WIP causes `StopIteration` while resolving `CalculationSourceDiagnostic` in `src/cadrumo/application/aggregation/_modelo_bindings.py`. No unrelated source was changed.

For measurement only, the previously validated real 8,505-record manifest was reused to avoid treating that peer-WIP projection failure as a shipped artifact. The diagnostic bundle is `C:\Users\hello\AppData\Local\Temp\aeat-rung2-current-20260806\bundle-alias-manifest-reuse.json`, SHA-256 `1cb0...47f12`, 2,138,574 bytes, with 114 vocabulary entries, 153 query tokens, and matrix SHA-256 `d102...6bbfda`. It records the current provider, model, tokenizer, and authority provenance. Semantic replay is 22/32 hits (miss rate 0.3125); composed coverage is 93/123 (0.7560975609756098) with ten insufficient-coverage misses, so the alias additions do not clear the acceptance gate and do not change the standing rejected decision.

This is diagnostic evidence only. No Rung-2 matrix was accepted, no browser configuration was enabled, no locale or deployment artifact was promoted, and P02.S32 remains open pending a fresh authoritative projection and a passing remeasurement.
