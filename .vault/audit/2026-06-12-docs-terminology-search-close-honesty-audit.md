---
tags:
  - '#audit'
  - '#docs-terminology-search'
date: '2026-06-12'
modified: '2026-08-26'
body_hash: 'sha256:702f42b3ef0bac3e2df3e7455ceb21564040e67d9e0f8bfcf88e10bbeb23bea9'
related:
  - '[[2026-06-10-docs-terminology-search-adr]]'
  - '[[2026-06-10-docs-terminology-search-plan]]'
  - '[[2026-06-12-docs-terminology-search-rung2-adjudication-audit]]'
---

# `docs-terminology-search` audit: `campaign close honesty review`

## Review Scope

Fresh-context close review over the docs terminology search campaign before structural completion is declared. Evidence checked: the accepted ADR D1-D9, the L4 plan, the exec-record directory, the committed terminology/search surfaces, the S30 rung-2 adjudication, the codified project rules, and focused verification commands.

## Verified Complete

- Plan/exec consistency: the plan has 32 step rows and the exec directory has 32 matching step records. Before this S32 closeout, only `W05.P14.S32` remains open.
- Upstream prerequisite: `W01.P01.S01` tracks upstream vaultspec-rag issue `https://github.com/operator/vaultspec-rag/issues/185` and upstream link-back comment `https://github.com/operator/vaultspec-rag/issues/185#issuecomment-4687704833`.
- Handbook foundation: the bundled Terminology Handbook compiles and now carries 115 concepts, including the S31 self-hosted architectural concepts.
- Search compilation surfaces: concept cards, casilla projection, CLI projection, target resolution, wrangling, sweep, relevance data, synonym mining, held-out miss-rate, and unified records pass the `src/aeat/terminology` plus `dev/docs/terminology` test slice.
- Curation honesty: the ratchet remains clean at 75 draft concepts and 75 empty short descriptions against the 75/75 baseline.
- Codification: the three ADR candidates are project rules and are synced into provider-facing rule folders: `terminology-single-declaration`, `terminology-scaffold-preserve-contract`, and `shipped-search-licence-clean`.

## Findings

### CLOSE-001 | VERIFIED | Plan state no longer under-reports completed work

The original handover problem was a plan/exec mismatch. That mismatch is now reconciled: all implemented steps have checked rows, and every row has a corresponding exec record. The only row intentionally open during this audit is S32 itself.

### CLOSE-002 | VERIFIED | ADR codification candidates are promoted

The three ADR candidates satisfy the codify durability criteria: each is constraint-shaped, project-bound, and exercised by the completed implementation/review cycle. Existing-rule search found no terminology-specific duplicate. The rules were scaffolded through `vaultspec-core spec rules add`, authored with Rule/Why/How sections, verified with `vaultspec-core spec rules show`, and synced with `vaultspec-core sync`.

### CLOSE-003 | RESIDUAL | Relevance artifact remains a degraded sweep and must not be overclaimed

The S30 held-out harness reports 5 cases, 1 hit, 4 misses, 80.00% miss-rate, 76 failed compiled queries, and decision `refresh-relevance-first`. This is not a hidden completion blocker for the current plan because S30 explicitly adjudicated the deferred rung-2 gate on those measurements. It is a real operational follow-up: a future relevance refresh from a non-degraded resident RAG sweep is required before claiming the compiled relevance mapping has full held-out coverage or before justifying a static rung-2 embedding matrix.

Follow-up probe after plan closure confirmed this is still operationally unresolved: the resident service reported healthy with CUDA/models loaded, but a bounded live sweep over `prorrata`, `casilla`, `modelo-303`, and `recargo-equivalencia` did not complete before the 244-second command timeout. A full refresh remains deferred to a dedicated sweep window.

### CLOSE-004 | RESIDUAL | Vault-wide structure errors are unrelated to this feature

Feature-scoped vault checks still report pre-existing global structure issues outside this feature: unsupported `.vault/tmp`, the ledger hardening audit filename, and one live-censo exec filename. The docs-terminology feature frontmatter, links, dangling links, body-links, feature index, references, schema, and rename-integrity checks are clean.

## Closure Decision

The campaign-close honesty review has run before structural completion. S32 may close after its exec record and code-review entry are updated. The docs terminology plan can be structurally closed, with the S30 degraded-sweep refresh recorded as an operational follow-up rather than concealed as complete coverage.
