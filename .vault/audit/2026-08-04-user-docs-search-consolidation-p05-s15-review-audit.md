---
tags:
  - '#audit'
  - '#user-docs-search-consolidation'
date: '2026-08-04'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:94a30f1694148f4c80035c1cd69db969f8b45551b8d9c8d152345b8ee41dd5dc'
related:
  - "[[2026-08-01-user-docs-search-consolidation-plan]]"
---

# `user-docs-search-consolidation` audit: `P05.S15 legal search record injection review`

## Scope

Reviewed commit `6d6c86db83` against the accepted consolidation ADR, especially Update 1 (`.vault/adr/2026-08-01-user-docs-search-consolidation-adr.md:94-102`), the active P05 plan (`.vault/plan/2026-08-01-user-docs-search-consolidation-plan.md:61-68,88-93`), the S14 audit and execution record, and the S15 execution record (`.vault/exec/2026-08-01-user-docs-search-consolidation/2026-08-01-user-docs-search-consolidation-P05-S15.md:47-53`). Evidence was gathered with vaultspec-rag `search_vault`, working CLI semantic search, `get_code_file`, and exact `rg` over the current tree. The broken MCP `search_codebase` alias was not used, and no reindex was attempted.

The review covered the LEGAL enum/model and `legal:<id>` projection identity, validated-catalogue projection, generated legal-reference target authority and D1 `.html`/anchor semantics, BOE provenance separation, strict optional metadata, unified conversion and ranking/display maps, resolver paths, Pagefind content/meta/filter/boost/language behavior, per-kind sampling and stats, import ordering, and stale four-kind acceptance claims. The S15 model, projection, unified branch, and injector are internally coherent on those points where they use the generated legal-reference authority (`dev/docs/terminology/_search_record.py:39-164`, `dev/docs/terminology/_legal_projection.py:30-103`, `dev/docs/terminology/_unified_record.py:92-482`, `dev/docs/pagefind_inject.py:73-417`, `dev/docs/legal_reference.py:186-680`). The findings below are the source-level exceptions. No tests, Sphinx builds, Pagefind runs, live probes, deployment, sweeps, or reindexing were run; runtime acceptance remains pending by instruction.

## Findings

### P05.S15 legal search record injection review | high | Future legal resolution still bypasses the generated destination authority

`dev/docs/terminology/_resolution.py:396-430` routes normative-source and legal-TOML hits to `_legal_target`, whose record construction at `dev/docs/terminology/_resolution.py:434-456` uses the stable-looking id `legal:<legal_id>` but emits `SearchRecordKind.PAGE` and the direct BOE permalink as `target`. The S15 path uses that same identity namespace while emitting `SearchRecordKind.LEGAL` and the generated legal-reference target: `dev/docs/terminology/_legal_projection.py:30-72` obtains targets from `render_legal_reference()` and `dev/docs/terminology/_unified_record.py:453-482` preserves them. Consequently one legal id has two incompatible record shapes and destinations. The direct BOE URL violates D1's site-relative page/anchor contract (`.vault/adr/2026-07-15-docs-terminology-search-adr.md:294-303`) and Update 1's ruling that BOE permalinks are rendered at the generated legal destination (`.vault/adr/2026-08-01-user-docs-search-consolidation-adr.md:98-100`). This is a blocking authority split: future resolver output can bypass the destination rendered by the legal generator and disagree with the LEGAL record that Pagefind injects.

### P05.S15 legal search record injection review | medium | Deployment parity still excludes the emitted LEGAL kind

S15 now materialises legal records and carries them through the real injector (`dev/docs/pagefind_inject.py:163-168`), including a legal counter and per-kind sample bound (`dev/docs/pagefind_inject.py:73-98,344-369`). The deployed-artifact gate still defines `_DECIDED_RECORD_KINDS` as only `concept`, `casilla`, and `cli` (`dev/docs/tests/test_deployment_search_parity.py:78-87`). Its built-index, written-fragment, and localized-root assertions consume that stale set (`dev/docs/tests/test_deployment_search_parity.py:208-210,282-286,464-468`), so the gate can report parity while every shipped root omits LEGAL. That leaves the Update 1 per-kind deployment contract unproven and is the source-level acceptance gap that P05.S17 must close; no runtime result is inferred here.

### P05.S15 legal search record injection review | low | Four-kind claims remain in search review and build documentation

The new fifth kind is not reflected in several explanatory surfaces: `dev/docs/tests/test_pagefind_inject_site.py:143-151` still calls the projection four-kind and describes only concepts, casillas, and CLI; `dev/docs/tests/test_built_site_resolvability_sweep.py:3-8,145-151,187-190` still describes a four-kind/three-producer sweep; `dev/docs/build.py:419,459,493,741` still describes the injector as concept/casilla/CLI-only; `dev/docs/terminology/tests/test_unified_record.py:3-8` still names four projected kinds; and `dev/docs/terminology/_unified_record.py:348-350` omits legal from the `to_search_record` argument contract. These are stale claims rather than additional runtime behavior defects, but they can mislead future review and conceal the LEGAL surface.

### empty-legal-projection | low | PASS: mandatory legal surface now fails closed

Fresh RAG grounding over the injector, legal projection, and all-kind materialisation gate identified that the injector refused a skipped CLI projection but could continue with an empty legal projection. The materializer now raises `SearchInjectionError` before injection when the decided legal projection is empty. This protects the fifth `LEGAL` kind at source level; P05.S14-S17 still require their generated-surface, parity, build, and runtime evidence.

## Recommendations

Source review outcome: FAIL. Before S15 can be accepted, route all resolver-produced legal hits through the same validated legal projection/generated renderer, emitting `SearchRecordKind.LEGAL` with the generated site-relative target and retaining the BOE permalink only as typed destination provenance. Then add LEGAL to the deployment parity inventory and reconcile the stale four-kind claims. P05.S16 must also reconcile existing legal relevance targets and replace the BOE-only target-resolution branch (`dev/docs/terminology/tests/test_relevance_data.py:171-173`) with the generated legal target inventory; P05.S17 must prove per-kind anchor and destination-grounding parity. Runtime/build acceptance remains open.

## Follow-up review: remediation `b68f56f11b9fc2c9b49edd3512ccbd8134591c22`

Re-reviewed `b68f56f11b9fc2c9b49edd3512ccbd8134591c22` at `HEAD` against accepted ADR Update 1 (`.vault/adr/2026-08-01-user-docs-search-consolidation-adr.md:94-102`), the P05 plan (`.vault/plan/2026-08-01-user-docs-search-consolidation-plan.md:61-68,88-93`), the S14 audit/exec, the S15 exec, and the preceding findings above. Re-grounding used vaultspec-rag `search_vault`, working CLI semantic searches, `get_code_file`, and exact `rg`; the broken MCP `search_codebase` alias was not used and no reindex was attempted. No tests, builds, Pagefind runs, live probes, deployment, sweeps, or reindexing were run.

The prior HIGH resolver finding is resolved: `dev/docs/terminology/_resolution.py:239-247` indexes the same generated legal projection used by injection, and `dev/docs/terminology/_resolution.py:444-455` returns that record with LEGAL kind, generated target, and BOE provenance metadata. The prior MEDIUM parity finding is resolved: `dev/docs/pagefind_index.py:77-91`, `dev/docs/tests/test_deployment_search_parity.py:78-85`, and the artefact assertions at `dev/docs/tests/test_deployment_search_parity.py:193-208,264-284,450-466` include LEGAL; the publish preflight also consumes the canonical set (`dev/deploy/docs_static_site.py:290-303`, `dev/deploy/tests/test_publish_preflight_search_records.py:205-218`).

### P05.S15 legal search record injection review | low | Residual stale-kind claims and coverage omissions remain

The remediation updates the previously cited build, injector, unified-record, and parity claims, but residual drift remains. `dev/docs/tests/test_built_site_resolvability_sweep.py:42-43` still says the narrowed sweep renders only casilla, glossary, and CLI destinations even though the preceding inventory names LEGAL. `dev/docs/terminology/tests/test_display_class_coverage.py:57-79,117` still claims to mirror the full injected projection while constructing only concepts, casillas, and CLI; `dev/docs/terminology/tests/test_unified_record.py:162-180` still claims every kind is serialised while constructing only four kinds. The coverage model still says legal serialises as unified PAGE (`dev/docs/terminology/_coverage.py:225-229`), and the TOC-noise comment omits LEGAL (`dev/docs/terminology/_wrangle.py:231-233`). The shipped search-page gate descriptions also retain the old injected-card list (`dev/docs/tests/test_search_page_inline_ladder.py:6-9`, `dev/docs/tests/test_search_page_fulltext_class_ranking.py:3-5`). These are non-blocking documentation and coverage drift; the current resolver, projection, LEGAL ranking map, Pagefind inventory, and deployment inventory use the corrected fifth-kind path.

Follow-up outcome: PASS for blocking source findings; the residual LOW items should be reconciled before the audit narrative and display-class coverage are fully current. Runtime/build acceptance remains pending by instruction.

Follow-up recommendation: update the remaining scoped descriptions and add a real legal record to the unified/display-class coverage helpers, or state their intentionally narrowed fixture scope explicitly. Keep the prior runtime/build acceptance boundary unchanged.

## Final follow-up review: remediations `b68f56f11b9fc2c9b49edd3512ccbd8134591c22` and `86727ce0e9d5d811d2ed72425c05f85bcbba1b49`

Re-reviewed both remediation commits at the current `HEAD` against accepted ADR Update 1 (`.vault/adr/2026-08-01-user-docs-search-consolidation-adr.md:94-102`), the active P05 plan (`.vault/plan/2026-08-01-user-docs-search-consolidation-plan.md:65-68,93`), the S14 audit/exec records, the S15 exec record, and this audit. Re-grounding used vaultspec-rag `search_vault` for those records, working CLI semantic search, current `get_code_file`, and exact `rg`; the broken MCP `search_codebase` alias was not used and no reindex was attempted. No tests, builds, Pagefind runs, live probes, deployment, sweeps, or reindexing were run.

The prior HIGH resolver finding is resolved. `dev/docs/terminology/_resolution.py:239-247,404-455` indexes the same `project_legal_search_records()` projection used by Pagefind and returns its unified `SearchRecordKind.LEGAL` record, so normative and legal-catalogue hits now carry the generated site-relative page/anchor target and BOE provenance metadata. The prior MEDIUM deployment-parity finding is resolved: `dev/docs/pagefind_index.py:77-91`, `dev/docs/tests/test_deployment_search_parity.py:78-85`, its built-fragment and localized-root assertions, and the publish preflight consume the four-kind injected inventory including `legal`.

The prior LOW coverage and stale-kind findings are materially resolved. `dev/docs/terminology/tests/test_display_class_coverage.py:12-16,57-79,108-122` now calls the real legal projection and includes its records in the unified display-class corpus. `dev/docs/terminology/tests/test_unified_record.py:131-146,182-203` directly funnels a real registry-backed `LegalSearchRecord` and includes it in the all-kind shape check. The coverage model and TOC discriminator are corrected (`dev/docs/terminology/_coverage.py:82-87,256-276,419-431`; `dev/docs/terminology/_wrangle.py:231-242`), and the Pagefind/search-page/build documentation now names LEGAL where it describes the production surface.

### P05.S15 legal search record injection review | low | Built-site sweep prose still omits the LEGAL destination from its final scope sentence

`dev/docs/tests/test_built_site_resolvability_sweep.py:38-44` correctly identifies CONCEPT, CASILLA, LEGAL, and CLI destinations and the implementation at `dev/docs/tests/test_built_site_resolvability_sweep.py:148-160` walks the unified projection. Its final narrowing sentence nevertheless says it renders only the casilla, glossary, and CLI destinations in full, omitting the generated legal-reference pages. This is documentation drift only; it does not remove legal records from the sweep.

### P05.S15 legal search record injection review | low | The all-kinds materialisation gate does not assert that the mandatory LEGAL kind is present

`dev/docs/tests/test_pagefind_inject_site.py:143-162` says it proves all five kinds and describes legal as a priority surface, but its assertions require only `materialised.concepts`, `materialised.casillas`, and either CLI output or a CLI skip, followed by `{"concept", "casilla"} <= kinds`. It does not assert `materialised.legal_provisions > 0` or `"legal" in kinds`. The direct real-record checks in `dev/docs/terminology/tests/test_unified_record.py:131-146` and `dev/docs/terminology/tests/test_display_class_coverage.py:68-78` provide non-vacuous legal coverage elsewhere, so this remains a non-blocking gate-strengthening gap rather than evidence that the producer is currently omitting LEGAL.

### P05.S15 legal search record injection review | low | P05.S16 relevance gates still describe BOE permalinks as search targets

The current producer path keeps the BOE URL as typed provenance (`dev/docs/terminology/_search_record.py:133-164`, `dev/docs/terminology/_legal_projection.py:30-72`, `dev/docs/terminology/_unified_record.py:453-487`) and emits the generated destination. The separately scoped relevance surfaces have not yet been reconciled: `dev/docs/terminology/tests/test_sweep.py:143-156` still requires a `boe.es` legal target, `dev/docs/terminology/tests/test_relevance_data.py:12-14,123-179,371-373` still inventories/accepts legal permalinks, and the committed relevance artifact still contains BOE targets (`src/cadrumo/_data/terminology/relevance/relevance.json:51-52`). The active plan explicitly assigns this reconciliation and the no-unemitted-target gate to P05.S16 (`.vault/plan/2026-08-01-user-docs-search-consolidation-plan.md:67`), so it is not a new S15 producer or authority split; it remains an open P05 follow-up and must not be described as complete.

The three-kind wording in the deployment preflight narratives (`dev/deploy/docs_static_site.py:280-288`, `dev/deploy/tests/test_publish_preflight_search_records.py:3-13`) is historical wording about the pre-LEGAL pages-only incident, not a current inventory claim. Likewise, the three-record fixture in `dev/deploy/tests/test_published_delivery_content.py:59-67,109-111` is explicitly a count-difference mutation fixture, while canonical deployment parity covers all four injected kinds; neither is counted as a residual S15 finding.

Final follow-up outcome: PASS for S15 blocking source findings. The HIGH resolver conflict and MEDIUM parity omission are resolved; only the LOW residuals above remain. This PASS does not close the planned P05.S16 relevance reconciliation, P05.S17 legal parity, or runtime/build acceptance, all of which remain pending by instruction.

Final follow-up recommendation: correct the two LOW wording/assertion gaps and complete P05.S16/S17 before declaring the broader P05 phase closed. Preserve the source-only and runtime-pending boundary recorded above.

## Final S15 outcome: remediation `16bd128e41a778716dd172353da5d01db2bbe415`

Re-reviewed `16bd128e41a778716dd172353da5d01db2bbe415` at `HEAD`, on top of the previously reviewed `b68f56f11b9fc2c9b49edd3512ccbd8134591c22` and `86727ce0e9d5d811d2ed72425c05f85bcbba1b49`. Re-grounding used vaultspec-rag `search_vault` for the accepted ADR Update 1, active P05 plan, S15 audit, and S15 exec record, then current `get_code_file` and exact `rg` for both changed gates. No tests, builds, Pagefind runs, live probes, deployment, sweeps, or reindexing were run; no source was edited and the audit remains uncommitted.

The two residual S15 gate gaps are resolved. `dev/docs/tests/test_built_site_resolvability_sweep.py:38-44` now names the generated legal-reference pages in the narrowed user-scope rendering statement, while `dev/docs/tests/test_built_site_resolvability_sweep.py:145-160` walks the same unified concept/casilla/legal/CLI projection. `dev/docs/tests/test_pagefind_inject_site.py:143-163` now requires `materialised.legal_provisions > 0` and requires `legal` in the materialised kind set. These changes close the prior LOW wording and mandatory-LEGAL-assertion findings without changing the production path.

The earlier HIGH resolver conflict and MEDIUM deployment-parity omission remain resolved as recorded above. No blocking S15 source finding remains.

The remaining BOE-target issue is deliberately outside this final S15 gate cleanup: P05.S16 still owns reconciliation of the committed legal relevance targets and the target-resolution gate (`.vault/plan/2026-08-01-user-docs-search-consolidation-plan.md:67`). The current producer continues to use generated site-relative legal targets with BOE provenance, while the unreconciled relevance artifact and its assertions still contain BOE destination URLs (`dev/docs/terminology/tests/test_sweep.py:143-156`, `dev/docs/terminology/tests/test_relevance_data.py:12-14,123-179,371-373`, `src/cadrumo/_data/terminology/relevance/relevance.json:51-52`). This is the previously recorded, explicitly pending S16 follow-up, not a new S15 authority split. P05.S17 remains separately pending for legal per-kind anchor and destination-grounding parity (`.vault/plan/2026-08-01-user-docs-search-consolidation-plan.md:68`); this review supplies no runtime or parity result.

Final outcome: PASS for S15 source review. The two changed gates now verify the legal projection and generated legal destination scope; only the deliberately pending P05.S16 relevance reconciliation, P05.S17 parity gate, and runtime/build acceptance remain open.

### Current P05.S16 static reconciliation note (2026-08-05)

Fresh vaultspec-rag grounding over the P05 execution records, the legal projection, the generated legal-reference authority, and the current relevance artifact identified that the earlier BOE-target finding is now historical rather than current source state. The current JSON contains 112 mappings, 724 total target slots, and 336 legal target slots; all 336 legal slots carry `kind: legal`, `surface: legal`, generated `_generated/legal/` targets, and no direct `boe.es` search target. The P05.S16 execution record also records removal of the two stale `legal:rd-1007-2023` objects without inventing replacement identities.

This note supersedes the earlier pending-S16 wording for the static artifact state. P05.S16 and P05.S17 remain plan-open until their authorized target/parity gates and runtime/build evidence are executed; no tests, builds, Pagefind runs, live probes, deployment, sweeps, or reindexing were run here.
