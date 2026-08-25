---
tags:
  - '#audit'
  - '#user-docs-search-consolidation'
date: '2026-08-04'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:4027701ba49edbc2d49820fe04f5d19994b5e58ae5abed512d70160177e68ce0'
related:
  - "[[2026-08-01-user-docs-search-consolidation-plan]]"
---

# `user-docs-search-consolidation` audit: `P05.S16 legal relevance reconciliation review`

## Scope

Focused formal source review of commit `003495eb646bc8de1ec60b98c0166c2d125701a8`, limited to `src/cadrumo/_data/terminology/relevance/relevance.json`, `dev/docs/terminology/tests/test_relevance_data.py`, `dev/docs/terminology/tests/test_sweep.py`, and the P05.S16 execution record. Grounding used `vaultspec-rag` searches for the accepted ADR and Update 1, the active P05 plan, the S16 execution record, and prior P05 audit context, followed by `get_code_file`, working-CLI semantic search, and exact `rg` against the canonical legal projection, resolver, relevance artifact, and scoped tests. The broken `search_codebase` alias and issue #350 were not bypassed; no reindexing or runtime activity was performed. Static AST parsing of both scoped Python files and `git diff --check` passed.

## Findings

### p05-s16-legal-relevance-reconciliation | high | Two committed legal base IDs are not emitted by the canonical projection

The artifact still contains `legal:rd-1007-2023` at `relevance.json:3281-3285` and `relevance.json:6111-6115`, both with the generated page target `_generated/legal/boe-a-2023-24840.html`. The registry-backed projection assigns IDs through `legal_target_record_id(record.legal_id)` and the validated catalogue has provision IDs `rd-1007-2023:art-3` and `rd-1007-2023:df-4`, not the base `rd-1007-2023` ID. Consequently `test_relevance_data.py:220-258` constructs no expected target for either slot and deliberately appends both as unresolved before its fail-closed assertion. This violates the accepted Update 1 dead-target contract and the P05 verification requirement that the dead-target count be zero. The prorrata-only resolver check in `test_sweep.py:140-190` does not cover these two shipped mappings. Remediation is required at `relevance.json:3281-3285` and `relevance.json:6111-6115`: reconcile each mapping to the correct emitted provision ID and matching generated target, or remove it if no faithful provision correspondence exists; do not add a resolver alias for the non-emitted base ID. Update the S16 execution record after that authority decision and revalidation.

## Recommendations

Formal outcome: **FAIL — HIGH blocking finding**. P05.S16 must not close. The implementation correctly makes the stale IDs fail closed and the execution record truthfully discloses the unresolved state, but the committed relevance artifact still cannot satisfy its own target-resolution gate. No tests, builds, Pagefind, sweeps, live probes, deployment, or reindexing were run.

## Final S16 outcome: remediation `7783ccfd2a273e0520cc60250bf777d1736637f1`

The remediation diff removes exactly the two prior `legal:rd-1007-2023` target objects from `src/cadrumo/_data/terminology/relevance/relevance.json`; it adds no object, alias, article reassignment, or resolver exception. Static `rg` invariants on the current artifact are 112 mappings, 724 target objects, 336 `legal` targets, zero direct BOE targets, and no `legal:rd-1007-2023`, `:art-3`, or `:df-4` replacement object. The unchanged gate in `dev/docs/terminology/tests/test_relevance_data.py` still builds its legal ID-to-target inventory from `project_legal_search_records()` and rejects any missing legal ID before the final unresolved assertion, so the prior HIGH condition has no remaining artifact input. AST parsing, `git diff --check`, and conflict-marker scanning passed; the gate itself was not executed.

The remediation execution record truthfully distinguishes the historical 726/338 counts from the current 724/336 artifact and records zero missing legal IDs. RAG grounding was refreshed against the accepted ADR Update 1, active P05 plan, S16 execution/audit records, and the S17 audit; the S17 audit still records its source-level **PASS** and remains unchanged.

Formal outcome: **PASS** for the source-only S16 remediation review. The prior HIGH finding is resolved, with no residual blocking or non-blocking source finding. Runtime acceptance remains unperformed by instruction; this follow-up does not close the plan step or claim test/build acceptance.

## Final S16 import-cycle review: remediation `a791bf77ee1bf4850e4fa238e1146016384da476`

The final source slice confirms one canonical `legal_target_record_id` implementation at `dev/docs/terminology/_legal_projection.py:30`, exported there at `:24`. `dev/docs/terminology/_coverage.py:53` imports that function and `:70` re-exports it; it contains no second definition. `_legal_projection.py` has no `_coverage` import. Static `rg` inspection of the package import edges shows the former `_legal_projection -> _coverage` back edge is absent: initialization proceeds through `_miss_rate -> _sweep -> _resolution -> _legal_projection`, then terminates in the legal renderer and shared search-record dependencies. The relevant ten Python modules parse successfully with AST inspection, and the remediation diff passes `git diff --check` and conflict-marker scanning.

The prior S16 PASS remains valid: this commit changes only the helper ownership/re-export topology and the execution-record explanation; it does not alter the remediated relevance artifact, legal identities, targets, or gate semantics. The updated execution record accurately preserves the historical pre-fix import note, documents the acyclic static path, and keeps the no-runtime-verification boundary explicit. No new source finding is present.

Formal outcome: **PASS** for the final source-only S16 review. The prior HIGH finding remains resolved, with no residual blocking or non-blocking finding. S16 runtime acceptance is still unperformed by instruction; no tests, builds, Pagefind, sweeps, live probes, deployment, or reindexing were run. The earlier S17 source-level **PASS** remains recorded and unchanged.
