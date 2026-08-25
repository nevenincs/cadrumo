---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:87869000087d111d0d4e4e074a7bc5d3888feb7173b55da1af3d5e3a2709b54f'
step_id: 'S89'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Delete the legacy inbound TUI implementation and tests without a compatibility facade

## Scope

- `src/cadrumo/adapters/inbound/tui`

## Description

- Delete the retired inbound TUI implementation, package root, and tests rather than preserving a compatibility surface.
- Move presentation tests to their canonical TUI owners before deleting their former files.
- Prove the retired package is absent from the filesystem, Git index, HEAD tree, import resolution, and live source references.

## Outcome

The retired inbound TUI package has no physical, tracked, importable, or referential presence. Canonical presentation tests live under `entrypoints.tui`; no shim, alias, re-export, or compatibility initializer remains.

The zero-remnant detector returns an empty result, the complete 63-test migration/import-hygiene gate passes, and independent review approved the deletion evidence.

## Notes

Implementation deletion landed in `ebeb4507a3`; final test relocation and deletion landed in `0acec93b1a0`. S88 owns the durable live-tree detector that prevents recurrence.
