---
tags:
  - '#exec'
  - '#user-docs-search-consolidation'
date: '2026-08-04'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:5cf6f5214a7480d2f19f2199642101eb454567089e9dcef8d0ae5c931fc9d031'
step_id: 'S17'
related:
  - "[[2026-08-01-user-docs-search-consolidation-plan]]"
---

# Add the legal per-kind parity gate proving anchor existence and destination-grounding coverage for every projected provision record

## Scope

- `dev/docs/tests/`

## Description

- Ground the accepted consolidation ADR, active P05 plan, S14/S15 audits, and
  S14/S15 execution records with `uvx vaultspec-rag` vault search.
- Ground the existing glossary, casilla, and CLI parity gates plus the legal
  renderer, legal projection, search record, and unified record with semantic
  code search and `get_code_file`, then confirm current symbols with `rg`.
- Add the real registry-backed LEGAL projection parity gate for unique unified
  records, renderer-owned page/anchor targets, page-level exceptions, and
  destination BOE grounding in the emitted legal RST.
- Preserve the source-only boundary: do not run tests, builds, Pagefind, live
  probes, sweeps, deployment, or reindexing.

## Outcome

Implemented the S17 legal per-kind parity gate in `dev/docs/tests/test_legal_anchor_parity.py`.
The gate exercises `project_legal_search_records()`, `render_legal_reference()`,
and `to_search_record()` against the live registry-backed source, asserts
substantive count parity and unique LEGAL identities, matches every projected
target to the renderer inventory, validates emitted anchors or legitimate
page-level targets, and verifies each authored BOE permalink in both the
destination grounding inventory and destination RST link source.

Static implementation checks passed: AST parsing of the new test, execution-
record readback, `git diff --check`, and conflict-marker scans over the two
owned paths. No runtime or test result is claimed.

## Notes

The broken MCP `search_codebase` alias remains tracked in vaultspec-rag issue
#350; no reindex or bypass was used. Runtime/test/build acceptance is deferred
explicitly by instruction and remains unresolved. Unrelated peer WIP,
including S16, was preserved and is not part of this change.

### 2026-08-06 authorized execution

The real legal parity gate ran as part of the marker-aware source run and the full selection returned `63 passed in 180.00s (0:03:00)`. The generated legal inventory, unified `LEGAL` records, anchors, and BOE destination grounding are therefore runtime-tested in the source tree. Strict multilingual Sphinx build acceptance remains separate and is still red.
