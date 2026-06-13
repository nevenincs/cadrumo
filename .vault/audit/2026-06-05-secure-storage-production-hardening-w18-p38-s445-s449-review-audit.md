---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# `secure-storage-production-hardening` `W18.P38.S445-S449` Review

## S445-S449-001 | PASS | Split modules delegate runtime custody

Reviewed `src/aeat/application/modelo/_work_create_policy.py`, `src/aeat/application/modelo/_work_plazo.py`, `src/aeat/application/modelo/_iva_wallet_seed.py`, `src/aeat/entrypoints/cli/_modelo_projection_cli.py`, and `src/aeat/entrypoints/cli/_modelo_iva_wallet_cli.py`.

The work-create policy reads its feature switch through centralized settings and delegates profile applicability to workflow/profile services. The plazo module delegates deadline/recargo policy to domain services and logs recoverable deadline failures at debug level. The IVA wallet seed facade delegates taxpayer lookup and persistence to application services. The CLI registrars emit schema-backed payloads and localized errors without owning secure storage routing.

## S445-S449-002 | PASS | Validation passed

Focused ruff passed for all five files and their focused CLI tests. IVA wallet integration tests passed with 18 selected tests. Modelo projection integration tests passed with 4 tests. Natural-key CLI tests passed with 5 tests. Locale audit passed through `python -m aeat.locales audit`.

Disposition: close `AFR-297` through `AFR-301` as `manifest-discovery`.
