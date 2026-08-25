---
tags:
  - '#exec'
  - '#user-docs-search-consolidation'
date: '2026-08-04'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:f05e21fa0f0092e78efe6a88db604ed5e7da7c897a56635cc1ccc52ac33868a0'
step_id: 'S15'
related:
  - "[[2026-08-01-user-docs-search-consolidation-plan]]"
---

# Project the legal catalogue into the fifth search record kind with D1-conformant targets on the new surface and inject it beside the existing kinds with declared weights

## Scope

- `dev/docs/pagefind_inject.py`

## Description

- Add the strict `LEGAL` record kind and registry-backed legal projection using
  generated site-relative page/anchor targets.
- Carry authored catalogue metadata and BOE provenance through the unified
  record, with the declared legal display/ranking weight and injector filters.
- Route resolver-produced legal hits through the same generated target
  authority and align the emitted-kind inventories with `LEGAL`.
- Reconcile five-kind coverage, sweep, build, and search-page descriptions and
  require the legal projection in the all-kinds injection gate.
- Re-review the complete source slice after each remediation commit.

## Outcome

S15 landed through commits `6d6c86db83`, `b68f56f11b9fc2c9b49edd3512ccbd8134591c22`,
`86727ce0e9d5d811d2ed72425c05f85bcbba1b49`, and
`16bd128e41a778716dd172353da5d01db2bbe415`. The final formal review returned
PASS for S15 source findings. `vaultspec-rag` semantic searches grounded the
accepted ADR Update 1, active P05 plan, S14/S15 records, and the review audit;
exact current source was read with `get_code_file` and confirmed with `rg`.

## Notes

The broken MCP `search_codebase` alias remains tracked in vaultspec-rag issue
#350; no reindex or bypass was used. P05.S16 still owns reconciliation of the
committed BOE relevance targets, and P05.S17 still owns the legal parity gate.
No tests, builds, Pagefind runs, live probes, deployment, sweeps, or
reindexing were run. Runtime acceptance remains pending by instruction.

### 2026-08-05 source continuation: exact legal provision resolution

RAG-grounded source review identified that legal catalogue TOML hits still selected the first declared provision when a file contained multiple `[legal."..."]` tables. Commit `98a1a109f9` removes that `declared[0]` fallback. `TargetResolver` now reads only source table spans, requires the RAG hit line range to overlap exactly one catalogue provision, and drops invalid, unreadable, outside-table, ambiguous, or non-authoritative hits as `NO_TARGET_ENTITY`. The resolved record still comes from the generated legal-reference projection; the BOE permalink remains typed provenance and is never the search target.

Unexecuted real-behaviour coverage was added for precise resolution/provenance, cross-table ambiguity, `[sources]` ranges, and invalid ranges in `dev/docs/terminology/tests/test_resolution.py`.

Static verification only: RAG grounding, Ruff, basedpyright, `git diff --check`, and conflict-marker scanning passed. The existing whole-file format check remains red on pre-existing baseline drift. No tests, builds, Pagefind runs, sweeps, reindexing, live probes, deployment, or generated artifacts were run. P05.S15 remains open for runtime/build acceptance.

### 2026-08-05 source follow-up: legal test contract alignment

RAG review found a stale test description that still documented the removed file-level first-provision fallback. Commit `26d0dfce9f` now gives the example an explicit `iva.toml` source range (lines 1-20), asserts the resolved legal id, and documents the fail-closed behavior for absent, invalid, or multi-table ranges.

Static verification only: RAG grounding, Ruff, basedpyright, and `git diff --check` passed. Tests, builds, sweeps, reindexing, and deployment remain deferred.

### 2026-08-05 source continuation: fail closed on an empty legal projection

Fresh vaultspec-rag grounding over the injector, legal projection, and all-kind materialisation gate identified a remaining source-level omission: the injector already refused a skipped CLI projection but could continue if the registry-backed legal projection returned no records. The materializer now raises `SearchInjectionError` before record injection when the decided legal projection is empty. This preserves the fifth `LEGAL` kind as a mandatory source surface; it does not replace the generated-page, parity, build, or runtime gates owned by P05.S14-S17.

Static evidence only: vaultspec-rag grounding, AST parsing, and focused diff checks. No tests, builds, Pagefind runs, generated artifacts, live probes, reindexing, deployment, or runtime acceptance were run.

### 2026-08-05 LUNA Max legal projection re-audit

Fresh vaultspec-rag grounding and an independent LUNA Max review of the disjoint `dev/docs/terminology/_legal_projection.py` seam found no source defect and made no edit. The projection emits all validated legal records, takes generated targets only from the renderer inventory, fails closed on missing targets, and preserves BOE permalinks as provenance rather than search destinations. Ruff, basedpyright (0 errors, 0 warnings, 0 notes), and focused `git diff --check` passed for the owned file. P05.S15 remains open for its separate generated-surface, build, parity, and runtime gates; no tests, builds, Pagefind, generated artifacts, probes, sweeps, reindexing, deployment, or model downloads were run.

### 2026-08-06 authorized execution

The unified Pagefind projection contains 594 dedicated `LEGAL` records with renderer-owned BOE targets and permalink metadata. The full English Pagefind build reported 8,496 injected term/casilla/legal/CLI records, and the marker-aware legal/resolution gates are included in `63 passed in 180.00s (0:03:00)`. No legal provision is represented as a generic `PAGE` record in the authoritative projection.
