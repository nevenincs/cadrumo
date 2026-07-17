---
tags:
  - '#exec'
  - '#cli-persona-testimonials'
date: '2026-06-30'
modified: '2026-07-17'
step_id: 'S38'
related:
  - "[[2026-06-30-cli-persona-testimonials-plan]]"
---

# Run owner-aware touched-surface gates for W06 fixes and classify unrelated baseline or concurrent failures

## Scope

- `src/aeat`

## Description

- Run `uvx vaultspec-core vault plan check .vault/plan/2026-06-30-cli-persona-testimonials-plan.md`.
- Run `uvx vaultspec-core vault check all --feature cli-persona-testimonials`.
- Verify `vaultspec-rag` service readiness with `uvx vaultspec-rag server doctor`.
- Verify service-routed code search with
  `uvx vaultspec-rag search "WithholdingSourceResolver" --type code --port 8766 --limit 2`.
- Verify testimonial-risk code search with
  `uvx vaultspec-rag search "persona testimonial replay final messages calculation risk under declaration evidence" --type code --port 8766 --limit 3`.

## Outcome

S38 is complete.

The W06 touched surface is vault/orchestration only. S37 dispatched no code
fixer and no product files under `src/aeat` were changed, so there is no
campaign-owned product pytest or ruff surface to run for W06 fixes. Product test
coverage belongs to earlier code-bearing steps.

Gate results:

- Plan check passed.
- RAG doctor passed on the managed server backend: process alive on port `8766`,
  requests ready, CUDA available, cached models present, and provisioned Qdrant
  available.
- Service-routed code searches passed without `--allow-fallback`.
- Feature vault check is clean for campaign-owned categories after scoped
  cleanup: annotations, feature index, ADR status, schema, links, frontmatter,
  and markdown all pass.
- Feature vault check still exits non-zero on 32 pre-existing global
  `feature-rename-integrity` errors in unrelated exec folders. Those are not
  owned by W06 and were left unchanged.

## Notes

The RAG repair had two important operational findings. First, local-only search
could answer once but its local Qdrant code collection became inconsistent after
failed incremental writes and then produced `local_store_locked`, HTTP 500, and
array-shape errors. Second, the managed Qdrant backend is the viable path for
this repository-sized code index, but startup takes about two minutes while the
shared collection store loads. Short startup probes can misclassify it as port
silent before it is ready.
