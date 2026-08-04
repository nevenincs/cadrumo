---
tags:
  - '#exec'
  - '#user-docs-search-consolidation'
date: '2026-08-04'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:501d0733c0fe6c76e37620497ca02d4c591c5d617d093565c57c40972186e551'
step_id: 'S23'
related:
  - "[[2026-08-01-user-docs-search-consolidation-plan]]"
---

# Resolve casilla relevance hits at individual-record granularity and refuse file-level first-record fallback

## Scope

- `dev/docs/terminology/_resolution.py`

## Description

- Ground the resolver against the typed chunk-hit, projection, and target contracts.
- Parse registry TOML casilla declaration spans from the RAG hit's source line range.
- Resolve only one exact projected record and fail closed for model-only, unreadable, invalid, ambiguous, or stale hits.

## Outcome

Commits `18a777cc44` and `3fb2c90cae363b464daab7ef0efcf99f0be43d7f` remove the unsafe `records[0]` namespace representative and support the real quoted and unquoted revision-header spellings. A casilla hit now resolves only when its source section identifies one casilla and that casilla has one current projected record; otherwise it becomes a typed dropped hit with an explicit reason.

## Tracking

- Individual registry-section locator: complete.
- Ambiguous/file-level fallback removal: complete.
- Stale/unprojected target refusal: complete.
- Diseños or other non-TOML source locator: fail-closed pending a future typed locator contract.
- Formal review found that the section-header parser accepted only quoted revision keys while real registry files also contain unquoted revision headers; `3fb2c90cae363b464daab7ef0efcf99f0be43d7f` now accepts both forms.
- Re-sweep and exact target coverage measurement: pending P06.S24/P02; not run in this step.

## Notes

The implementation agents ran RAG discovery, owned-file history/diff checks, and `git diff --check`. The focused header correction is committed, but a fresh review and a post-change sweep/target gate are required. Tests, builds, Pagefind compilation, deployment, and live probes were not run. The step must not be marked closed until P06.S24 acceptance passes.
