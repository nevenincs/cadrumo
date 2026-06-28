---
tags: ['#exec', '#codebase-monolith-decomposition']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S27'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W02.P03.S27 - residual live verify extraction

Scope: `src/aeat/entrypoints/cli/_app_live.py` and `src/aeat/entrypoints/cli/_app_live_verify_cli.py`.

## Description

- Added focused `_app_live_verify_cli` command module for `app live verify`.
- Moved `list`, `view`, `latest`, `nif-iva`, and `tgvi` commands plus verify row rendering out of `_app_live.py`.
- Registered verify through a registrar that receives active-bucket and expected-verdict helpers from the live façade.
- Preserved `verify_app` as a top-level `_app_live` façade export for existing tests and consumers.

## Outcome

Extraction completed. The live root now delegates verify command registration to `_app_live_verify_cli`.

## Notes

No business logic was added to the CLI. Persistence remains in `VerifyService`; live access remains gated by `AeatAccessGate`.
