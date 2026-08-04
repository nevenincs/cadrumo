---
tags:
  - '#exec'
  - '#user-docs-search-consolidation'
date: '2026-08-04'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:581f321efc8b151cf8baa3031fb1c3c1e2985f7963f74ed5b2719831cfc70786'
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
