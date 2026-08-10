---
tags:
  - '#exec'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:9fd3d2b47548d484531aff3c4b0b8e9fe480232446ef0a9854938779b02cad3e'
step_id: 'S11'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---
# Publish complete generated trees and provenance atomically from an isolated temporary target

## Scope

- `dev/registry/`

## Description

- Move the canonical provenance manifest into the generated `export/` directory and exclude only that internal JSON member from TOML output digests.
- Require the internal manifest through isolated S10 validation, refuse the former sibling manifest, and prove the real TOML loader ignores the JSON member.
- Add a revision-export-only cutover with explicit roots, containment, link, junction, overlap, completeness, and stale-surface refusals.
- Journal and lock the transaction outside revision authority; use opaque registry-root backups, recovery, post-cutover digest and loader checks, and rollback deletion.
- Add real Windows filesystem proofs for first manual-target cutover, no target, invalid candidates, locked mid-swap restoration, interrupted verified-candidate recovery, provenance placement, stale-sibling refusal, and no legacy reader or copy API.

## Outcome

- Generated output now publishes only `revisions/<id>/export/`, preserving the revision's non-export TOML authority byte-for-byte.
- Provenance moves atomically with generated TOML as `_generation.provenance.json`; validation requires it while the production loader ignores JSON.
- Existing manual exports are opaque rollback sources for the first hard cutover and are never parsed, copied, merged, or retained after a successful verified replacement.
- Formal re-review found no remaining critical, high, or medium issue.

## Notes

- Focused S10/S11 proof: 27 passed. Full `dev/registry/tests` proof: 80 passed before the final recovery additions; the final focused recovery gate passed after them.
- Scoped Ruff, Ruff format, and basedpyright were clean. No shipped registry tree was mutated.
