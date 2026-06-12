---
tags:
  - '#exec'
  - '#docs-terminology-search'
date: '2026-06-10'
step_id: 'S32'
related:
  - "[[2026-06-10-docs-terminology-search-plan]]"
---




# Run the campaign honesty review before structural completion is declared and promote the three ADR codification candidates (terminology-single-declaration, terminology-scaffold-preserve-contract, shipped-search-licence-clean) through the codify phase

## Scope

- `.vault audit + .vaultspec rules pipeline`

## Description

- Ran a fresh campaign-close honesty review against ADR D1-D9, the plan, exec records, test evidence, codified rules, and feature vault checks.
- Promoted the three ADR codification candidates through the `vaultspec-codify` workflow: `terminology-single-declaration`, `terminology-scaffold-preserve-contract`, and `shipped-search-licence-clean`.
- Verified the codify durability criteria: each candidate is constraint-shaped, project-bound, and exercised by the completed docs terminology implementation/review cycle.
- Searched existing rules before authoring and found no terminology-specific duplicate coverage.
- Scaffolded each rule with `vaultspec-core spec rules add`, authored Rule/Why/How bodies, verified each rule with `vaultspec-core spec rules show`, and synced provider-facing rule outputs with `vaultspec-core sync`.
- Persisted the close honesty review as `.vault/audit/2026-06-12-docs-terminology-search-close-honesty-audit.md`.

## Outcome

S32 is satisfied. The campaign honesty review has run before structural completion is declared, and the three ADR codification candidates are now project rules. The review confirms the original plan/exec mismatch is resolved: the plan has 32 step rows and 32 matching exec records, with only S32 open at audit time. It also records the real residual risk from S30: the current relevance artifact is a degraded sweep and needs a future non-degraded refresh before anyone claims full held-out relevance coverage or implements rung-2 embeddings.

Files touched for this step: `.vaultspec/rules/rules/project/terminology-single-declaration.md`, `.vaultspec/rules/rules/project/terminology-scaffold-preserve-contract.md`, `.vaultspec/rules/rules/project/shipped-search-licence-clean.md`, provider-synced rule copies under `.claude/rules`, `.codex/rules`, and `.gemini/rules`, `.vault/audit/2026-06-12-docs-terminology-search-close-honesty-audit.md`, and this exec record.

## Notes

Verification run:

- `uv run vaultspec-core spec rules list`: shows `project/terminology-single-declaration.md`, `project/terminology-scaffold-preserve-contract.md`, and `project/shipped-search-licence-clean.md`.
- `uv run vaultspec-core spec rules show terminology-single-declaration`: verified wording.
- `uv run vaultspec-core spec rules show terminology-scaffold-preserve-contract`: verified wording.
- `uv run vaultspec-core spec rules show shipped-search-licence-clean`: verified wording.
- `uv run vaultspec-core sync --json`: created provider-facing copies of the three rules and left existing synced files unchanged.
- `uv run python -c '<plan/exec coverage check>'`: 32 plan rows, 31 checked before S32, 32 exec records, no missing exec records.
- `uv run python -c 'from dev.docs.terminology import adjudicate_rung2, evaluate_held_out_miss_rate; ...'`: `cases=5 hits=1 misses=4 miss_rate=80.00% failed_queries=76 targeted_queries=1 decision=refresh-relevance-first`.
- `uv run python -m dev.docs.terminology.sweep --concept prorrata --concept casilla --concept modelo-303 --concept recargo-equivalencia --no-reindex --timeout 60`: timed out after 244 seconds; no full relevance refresh was completed in this closeout.

The shared worktree still contains unrelated dirty files from other streams. They were not modified for S32.
