---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:fe5dd9acad5ab0421326e8021eed219b9ac38259b42fec7a99bc657dff6577df'
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
- Production composition test resolves the definition and request contract through the public export facade.
- Independent review remains pending with S41 because the two steps are atomic for the CLI cutover.

## Notes

S44 remains open pending S41's real-plan test, Vault validation, and independent re-review. It has no shim or legacy alias.
