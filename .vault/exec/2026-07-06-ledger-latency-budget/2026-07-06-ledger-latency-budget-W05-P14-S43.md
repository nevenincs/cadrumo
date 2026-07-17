---
tags:
  - '#exec'
  - '#ledger-latency-budget'
date: '2026-07-06'
modified: '2026-07-17'
step_id: 'S43'
related:
  - "[[2026-07-06-ledger-perf-optimization-plan]]"
---

# Draft a follow-up ADR for dirty-set save semantics before implementation

## Scope

- `.vault/adr/2026-07-06-ledger-latency-budget-adr.md`

## Description

- Load the `vaultspec-adr` workflow and ADR template.
- Search for existing dirty-set ADR coverage and list current latency-budget ADRs.
- Scaffold a new ADR with `vaultspec-core vault add adr` related to the S42 research.
- Draft the proposed dirty-set save semantics ADR.
- Correct the S43 plan row to point at the CLI-scaffolded ADR path.
- Run scoped vault checks for frontmatter, placeholders, ADR status, body links, and schema.

## Outcome
- `.vault/adr/2026-07-06-ledger-latency-budget-adr.md` now proposes an additive dirty-set repository write contract.
- The ADR recommends keeping full reconciliation as fallback while adding a known-delta path for changed/new transactions, removals, and sibling secure-object writes.
- The ADR explicitly blocks implementation until operator acceptance.
- `vaultspec-core vault check frontmatter`, `vaultspec-core vault check placeholders`, and `vaultspec-core vault check body-links` passed.

## Notes

- The ADR-specific RAG search timed out after 49 seconds, and the concurrent code search hit the local Qdrant lock. Grounding continued from S42 semantic results and direct source reads.
- `vaultspec-core vault check all` failed on repository-wide pre-existing modified-stamp warnings.
- `vaultspec-core vault check adr-status` failed on repository-wide legacy ADR status warnings; the new ADR uses the canonical H1 proposed status.
- `vaultspec-core vault check schema` failed on unrelated older ADR/plan research-link findings; the new ADR has related research frontmatter and was not listed.
