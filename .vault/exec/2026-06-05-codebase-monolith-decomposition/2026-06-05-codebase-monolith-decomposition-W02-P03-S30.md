---
tags: ['#exec', '#codebase-monolith-decomposition']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S30'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W02.P03.S30 - residual modelo audit extraction

Scope: `src/aeat/entrypoints/cli/_modelo.py` and `src/aeat/entrypoints/cli/_modelo_audit_cli.py`.

## Description

- Added focused `_modelo_audit_cli` command module for `app modelo audit`.
- Moved `show`, `check`, `export`, and `replay` commands plus audit-specific bundle helpers out of `_modelo.py`.
- Preserved `audit_app` as a top-level `_modelo` façade export.
- Mounted audit through `register_audit_commands(app)`.
- Restored the shared `_active_bucket_id` helper in `_modelo.py` for iva-wallet and m036 registrars.

## Outcome

Extraction completed. The modelo root now delegates audit command registration to `_modelo_audit_cli`.

## Notes

Evidence bundle behavior remains in `application.evidence.EvidenceBundleService`; the CLI module only adapts command arguments and payload emission.
