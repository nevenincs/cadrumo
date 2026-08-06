---
tags:
  - '#exec'
  - '#user-docs-search-consolidation'
date: '2026-08-06'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:1df74682d6d1355dbc7be8bd3b00813fe8276026953b3d23374cf60ca792256f'
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
