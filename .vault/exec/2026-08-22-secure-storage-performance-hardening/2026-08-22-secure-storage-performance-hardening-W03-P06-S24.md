---
tags:
  - '#exec'
  - '#secure-storage-performance-hardening'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:c1331429ce5122c0de60210ffbbbbc235a3f83fd73d72f15f6a3b0df525e8e08'
step_id: 'S24'
related:
  - "[[2026-08-22-secure-storage-performance-hardening-plan]]"
---
# Reuse the anchored discovery observation instead of reopening and revalidating commit members

## Scope

- `src/cadrumo/adapters/persistence/storage/custody/_capsule_discovery.py`

## Description

- Return one frozen `AnchoredCurrentCapsuleCommit` per discovered capsule with
  the parsed commit retained from its anchored bounded read.
- Preserve deterministic UUID ordering and retired-layout refusal.
- Project identity-only callers from retained observations and build internal
  summary witnesses without reopening or reparsing commit markers.
- Read only the separately UUID-bound label provenance needed by the witness.

## Outcome

Implemented in `ec72219bb3`. Independent current-HEAD verification passes 65
focused capsule and path-identity tests. Ruff over the three changed files and
`git diff --check` pass.

## Notes

Tests prove exactly one commit parse per candidate, deterministic witness order,
foreign-label refusal, and no custody-envelope or sentinel read. Independent
review found anchored POSIX and Windows safety preserved, the retired
`anchored_current_capsule_ids` surface absent, one owner for the new observation,
no P07 public API redeclaration, and no MEDIUM or HIGH finding.
