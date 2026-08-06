---
tags:
  - '#exec'
  - '#core-authority'
step_id: S26
date: '2026-05-31'
modified: '2026-07-17'
body_hash: 'sha256:21355c7d34cbb998599950caa067cfde98a17d5f88a98522917f9f73a6fadc6e'
related:
  - '[[2026-05-31-core-authority-plan]]'
  - '[[2026-05-31-core-authority-adr]]'
---

# core-authority W03.P08.S26 — Rename SCHEMA_VERSION to ASSETS_SCHEMA_VERSION (RENAME-007)

## Change

Renamed `SCHEMA_VERSION` to `ASSETS_SCHEMA_VERSION` in
`src/aeat/domain/profile/assets/__init__.py`.

All internal uses updated (6 occurrences: 3 field defaults, 3 field validators).
No external callers exist — the constant is package-internal.

## Verification gate

`pytest src/aeat/domain/profile/assets -q` — 11 passed (via combined S26-S29 run).

## Commit

`5e2639336` — refactor(profile): disambiguate SCHEMA_VERSION to ASSETS_SCHEMA_VERSION and INVENTORY_SCHEMA_VERSION (RENAME-007)
