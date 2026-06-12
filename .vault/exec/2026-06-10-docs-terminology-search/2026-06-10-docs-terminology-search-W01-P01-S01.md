---
tags:
  - '#exec'
  - '#docs-terminology-search'
date: '2026-06-10'
step_id: 'S01'
related:
  - "[[2026-06-10-docs-terminology-search-plan]]"
---




# Deliver the upstream kick-off brief to the vaultspec-rag team requesting generic preprocess hook infrastructure - per-project file-pattern-to-preprocessor registration, a versioned preprocess output schema (extracted text or pre-chunked units with source metadata), cache invalidation keyed on source content hash plus preprocessor identity and version, explicit hard-fail versus skip-and-report failure semantics, and watcher/incremental integration - and track the upstream issue reference back into this plan (ADR D6)

## Scope

- `.vault/exec record + upstream vaultspec-rag issue tracker`

## Description

- Located the upstream package metadata for installed `vaultspec-rag` 0.2.19 and confirmed its bug tracker/repository is `wgergely/vaultspec-rag`.
- Verified the upstream repository has issues enabled and the current GitHub account has admin permission.
- Found the existing upstream kick-off issue `wgergely/vaultspec-rag#185` rather than filing a duplicate.
- Verified issue #185 covers the S01 contract: per-project preprocessor registration, versioned preprocess output schema, source/preprocessor/schema cache keying, explicit `skip-and-report` versus `fail` failure semantics, watcher integration, and size-limit interactions.
- Added upstream comment `https://github.com/wgergely/vaultspec-rag/issues/185#issuecomment-4687704833` linking the issue back to this AEAT docs-terminology-search workstream and its S02 interim sidecar path.
- Tracked the issue URL directly in the plan row.

## Outcome

S01 is satisfied. The upstream vaultspec-rag kick-off brief exists as `https://github.com/wgergely/vaultspec-rag/issues/185`, remains open, and contains the generic preprocess-hook requirements required by ADR D6 without AEAT-specific extraction logic leaking upstream. The AEAT workstream is linked from the upstream issue comment, and the local plan row now carries the upstream issue URL for future PM handoff.

## Notes

Verification run:

- `uv run python -c 'import importlib.metadata as m; ...'`: confirmed `vaultspec-rag` 0.2.19 and bug tracker `https://github.com/wgergely/vaultspec-rag/issues`.
- `gh repo view wgergely/vaultspec-rag --json nameWithOwner,url,viewerPermission,hasIssuesEnabled`: issues enabled, viewer permission `ADMIN`.
- `gh issue list --repo wgergely/vaultspec-rag --search "preprocess hook in:title,body" --state all --limit 20 --json number,title,state,url`: found open issue #185.
- `gh issue view 185 --repo wgergely/vaultspec-rag --json number,title,state,url,body,labels,createdAt,updatedAt`: confirmed coverage of the S01 requirement set.
- `gh issue comment 185 --repo wgergely/vaultspec-rag --body ...`: created upstream link-back comment `https://github.com/wgergely/vaultspec-rag/issues/185#issuecomment-4687704833`.

The shared worktree still contains unrelated dirty files from other streams. They were not modified for S01.
