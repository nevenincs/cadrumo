---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:1dd2e0929a1fff796b3bbd8de76f1da2c17ff8360ccd0e7a4665d0a5975f78fa'
step_id: 'S267'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---
# Reconcile feature and full Vaultspec warnings by exact document owner, removing scaffold annotations, reattesting modified bodies, refreshing indexes, and resolving only genuine corpus hygiene debt

## Scope

- `.vault/`

## Description

Run the feature-scoped and full-corpus Vaultspec health checks. Remove scaffold annotations and excess blank lines only from documents tagged `profile-password-custody`, reattest their changed bodies, refresh the feature index, and leave concurrent documents belonging to other features with their owners.

## Outcome

Seventeen feature-owned documents had generated annotations and matching markdown whitespace debt; the exact feature filters removed those annotations and normalized their markdown. The same seventeen body fingerprints were reattested. After creating this execution record, the `profile-password-custody` feature index was rebuilt again so it names all 337 current documents including S267. The final feature-scoped `vault check all` reports no diagnostics across structure, frontmatter, annotations, markdown, links, dangling links, body links, placeholders, orphans, features, execution mappings, sections, rename integrity, references, schema, ADR status, modified stamps, encoding, or naming.

## Notes

The full-corpus scan also reports warnings in active source-casilla, TUI, registry, CI, and other feature documents. Those are not this step's documents and were not mass-fixed in the shared worktree. S267 used exact feature ownership throughout and did not mutate unrelated vault records.
