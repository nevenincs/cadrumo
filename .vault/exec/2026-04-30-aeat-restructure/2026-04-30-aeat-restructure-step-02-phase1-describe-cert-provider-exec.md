---
tags:
  - "#exec"
  - "#aeat-restructure"
date: 2026-05-01
modified: '2026-05-01'
related:
  - "[[2026-04-30-aeat-restructure-adr]]"
  - "[[2026-04-30-aeat-restructure-plan]]"
  - "[[2026-04-30-aeat-restructure-step-02-phase1-secret-adapters-exec]]"
---

# 2026-04-30-aeat-restructure step-02 phase-1 describe_certificate_provider

## status

Step 2 PR 2 of 6. `__all__` removal of `auth._providers.describe_certificate_provider` per ADR Dead-code workstream / Phase 1.

## scope

- Remove `"describe_certificate_provider"` from `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_providers.py` `__all__` (line 353).
- Function definition stays at `_providers.py:268` — accessible via private API for tests but no longer on the public surface.

## pre-merge safety check

Unrestricted grep for `describe_certificate_provider` across the repo:

- Definition: `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_providers.py:268`.
- `__all__` entry: `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_providers.py:353` (this PR removes).
- Vault references: forensic-only (`.vault/research/`, `.vault/adr/`, `.vault/plan/`).

Zero external consumers in production source. Removal is safe.

## verification

`python -c "from aeat.adapters.outbound.aeat.auth._providers import describe_certificate_provider"` still succeeds (function definition retained); only the `__all__` export is removed.

## findings (FIX / FILE / STRIKE)

None additional — change is `__all__` removal only.

## next step

Step 2 PR 3 — `filing.utc_now` `__all__` removal.
