---
tags:
  - '#exec'
  - '#protected-browser-certificate-auth'
date: '2026-07-16'
modified: '2026-07-17'
body_hash: 'sha256:04b03503983a0b744317941639fa64032ab9d49d9db6d7472c94215fa4ba7ce4'
step_id: 'S04'
related:
  - "[[2026-07-16-protected-browser-certificate-auth-plan]]"
---
# Close Clave contexts and browsers when fresh-session persistence fails before ownership transfer

## Scope

- `src/cadrumo/adapters/outbound/aeat/auth/_clave_movil.py`
- `src/cadrumo/adapters/outbound/aeat/auth/_clave_permanente.py`

## Description

- Invalidate any partial encrypted session object when fresh persistence fails.
- Close the locally owned Cl@ve context and browser session before re-raising the primary persistence failure.
- Retain any resource whose bounded close fails so a later provider `close()` call can retry it.

## Outcome

Neither Cl@ve provider can orphan a successful fresh-login browser merely because encrypted persistence failed before normal ownership transfer.

## Notes

Fresh semantic search and exact inspection found matching persist-failure cleanup in both providers. The focused lifecycle matrix exercised production providers and real Playwright resources as part of 44 passing tests.
