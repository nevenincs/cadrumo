---
tags:
  - '#exec'
  - '#user-docs-search-consolidation'
date: '2026-08-04'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:4ae8dd83965c5fd94cf9def4129e45198990b46fdd38ffce519e9af5eb924db1'
step_id: 'S16'
related:
  - "[[2026-08-01-user-docs-search-consolidation-plan]]"
---

# Reconcile the committed legal relevance targets to the new record ids and extend the target-resolution gate to refuse any target id no injector emits

## Scope

- `src/cadrumo/_data/terminology/relevance/`

## Description

- Reconcile each existing `legal:` relevance target against the generated legal-reference renderer, preserving mapping order, record ids, surfaces, and ranking weights while setting the kind to `legal`.
- Extend the real target-resolvability gate with the injector-backed legal record-id-to-target inventory, rejecting missing ids, mismatched generated targets, non-LEGAL kinds, and direct BOE search targets while retaining non-legal drift and anti-tautology checks.
- Update the recorded prorrata sweep assertions to require exact generated legal destinations and independently verify BOE provenance on resolved search records.
- Run only JSON parsing, AST parsing, exact `rg` checks, `git diff --check`, and conflict-marker scanning.

## Outcome

Implemented the S16 relevance reconciliation and fail-closed legal target gate. The committed artifact retains all 112 mappings and 726 target slots; 338 legal slots now use renderer-generated destinations with `kind: legal`, including the page-level `_generated/legal/boe-a-2023-24840.html` target.

## Notes

- The current legal projection emits provision ids, not the two legacy `legal:rd-1007-2023` ids; the gate intentionally reports those missing ids as unresolved until the registry/relevance authority is reconciled. No alias or new mapping was invented.
- `dev.docs.terminology._legal_projection` cannot be imported in this dirty tree because of a pre-existing `_miss_rate`/`_legal_projection` circular import; the artifact targets were derived directly from the same `dev.docs.legal_reference` renderer authority without modifying that unrelated surface.
- Per instruction, no tests, builds, Pagefind runs, live probes, sweeps, deployment, or reindexing were run.

- Historical note status: the preceding `dev.docs.terminology._legal_projection` importability note records the pre-remediation state and remains historical evidence; the current static state is recorded below.

### Import-cycle remediation (2026-08-04)

RAG grounding and exact `rg` inspection confirmed the source-grounded cause: package initialization imports `_miss_rate`, which imports `_sweep`, which imports `_resolution`, which imports `_legal_projection`; `_legal_projection` previously imported `legal_target_record_id` from `_coverage`, while `_coverage` imports `_miss_rate`, closing the cycle before projection or gate execution.

The remediation defines `legal_target_record_id` once in `_legal_projection` and re-exports that same function object from `_coverage`. `_legal_projection` no longer imports `_coverage`; `_coverage` now imports the canonical helper from `_legal_projection`. No lazy import, helper module, duplicate implementation, legal identity change, target-authority change, coverage-semantics change, or injection change was introduced.

Static import-graph evidence shows the initialization path now terminates at the shared search-record and renderer dependencies: `_miss_rate -> _sweep -> _resolution -> _legal_projection`, with no reverse `_legal_projection -> _coverage` edge. Based on this static evidence, the current projection/gate path is importable after the fix; no runtime import or test result is claimed. AST parsing, exact `rg` inspection, `git diff --check`, and conflict-marker scanning remain the only verification boundary; no tests, builds, Pagefind runs, live probes, sweeps, deployment, or reindexing were run.

### 2026-08-06 authorized execution

The live RAG sweep was refreshed and promoted byte-identically: 112 mappings, 169 target rows, 91 unique record ids, 112 concept target rows, and 57 legal target rows. No stale legal ids and no synthetic `code:` targets remain. The marker-aware relevance-data and legal-anchor gates are part of `63 passed in 180.00s (0:03:00)`.

## Remediation addendum (2026-08-04)

RAG, source, and registry inspection found no canonical base `rd-1007-2023` record: the validated authority contains only `rd-1007-2023:art-3` and `rd-1007-2023:df-4`, and `project_legal_search_records` emits record ids from each canonical `record.legal_id`. The two stale `legal:rd-1007-2023` target objects were removed from their existing mappings; they were not reassigned to either provision because no canonical provision identity was available.

The strict S16 target gate now has no missing legal record ids: the committed relevance artifact contains no legal target id that the injector cannot emit. Prior notes and evidence remain unchanged. Verification was static-only: JSON parse/invariant comparison, AST/`rg`, `git diff --check`, and conflict-marker scanning; no tests, builds, Pagefind runs, live probes, sweeps, deployment, or reindexing were run.

### Post-remediation state

The earlier Outcome count of 726 total target slots and 338 legal target slots is historical, from before this remediation. The current remediated committed artifact contains 112 mappings, 724 total target slots, and 336 legal target slots: exactly two stale `legal:rd-1007-2023` objects were removed and none were reassigned. The strict injector-backed target gate now reports zero missing legal record IDs.
