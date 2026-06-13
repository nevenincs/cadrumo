---
tags:
  - '#exec'
  - '#core-authority'
step_id: S27
date: '2026-05-31'
modified: '2026-05-31'
related:
  - '[[2026-05-31-core-authority-plan]]'
  - '[[2026-05-31-core-authority-adr]]'
---

# core-authority W03.P08.S27 — Rename SCHEMA_VERSION to INVENTORY_SCHEMA_VERSION (RENAME-007)

## Change

Renamed `SCHEMA_VERSION` to `INVENTORY_SCHEMA_VERSION` in
`src/aeat/domain/profile/inventory/__init__.py`.

All internal uses updated (6 occurrences: 3 field defaults, 3 field validators).
No external callers exist — the constant is package-internal.

## Verification gate

`pytest src/aeat/domain/profile/inventory -q` — passed (via combined S26-S29 run).

## Commit

`5e2639336` — refactor(profile): disambiguate SCHEMA_VERSION to ASSETS_SCHEMA_VERSION and INVENTORY_SCHEMA_VERSION (RENAME-007)
