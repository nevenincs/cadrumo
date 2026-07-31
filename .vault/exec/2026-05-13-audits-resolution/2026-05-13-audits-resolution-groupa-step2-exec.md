---
tags:
  - '#exec'
  - '#audits-resolution'
date: '2026-05-13'
modified: '2026-07-17'
body_hash: 'sha256:391eac0b23e55f3b68feea99fd4c20ae8c70e5501caae8af0385171229eb198e'
related:
  - "[[2026-05-13-audits-resolution-plan]]"
  - "[[2026-05-13-eliminate-shims-audit]]"
---

# audits-resolution group-a step-2

## scope

Plan row A2: tighten `PersistedAuthSession` and `PersistedBrowserSession`.

Changes:

- `PersistedAuthSession` (in `src/aeat/application/auth/_sessions.py`):
  `extra="ignore"` flipped to `extra="forbid"` plus `strict=True`.
- `AuthenticatedAeatSessionResult` (same file): `strict=True` added.
- `PersistedBrowserSession`
  (`src/aeat/adapters/outbound/aeat/auth/_session_store.py`):
  `strict=True` added.

## verification

`pytest src/aeat/application/auth/ src/aeat/adapters/outbound/aeat/auth/ -q`
green with 139 passed.

`grep -n 'extra="ignore"' src/aeat/application/auth/_sessions.py`
returns nothing.
