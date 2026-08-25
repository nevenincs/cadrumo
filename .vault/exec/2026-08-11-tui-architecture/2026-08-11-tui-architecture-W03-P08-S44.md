---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:462f9cbe5bb1dbb0a2f6336b29d0d05700fb3df7645aaf12b59ca395ba7678be'
step_id: 'S44'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# Expose Google export operation definitions through the export application facade

## Scope

- `src/cadrumo/application/export/__init__.py`

## Description

- Expose the sole Google Sheets export definition builder, public registration builder, request/result contracts, safe remote result, and reusable application service from the export facade.
- Keep the facade free of Google adapters, storage repositories, credential construction, and entrypoint imports.
- Use the facade from the sole production composition seam and both migrated CLI consumers; no private `_google_operation` import or compatibility export was added.

## Outcome

The export facade is the only legal cross-package application surface for Google Sheets export contracts and construction. Concrete Google resources remain composed outside application ownership.

## Verification

- Scoped Ruff and `ty` checks pass.
- The real production composition fixed-point test resolves the definition and request contract through the public export facade.
- CLI schema and payload tests pass after both consumers cut over.

## Notes

S44 remains open pending independent re-review with its atomic S41 companion. It has no shim or legacy alias.
