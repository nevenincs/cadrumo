---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-05-secure-storage-production-hardening-W12-P26-S378]]'
---

# `secure-storage-production-hardening` `W12.P26.S378` Review

## S378-001 | PASS | Config CLI is a facade, not raw storage ownership

The current `_config/__init__.py` dispatches to application/domain services for profile
lifecycle, repair, auth, apoderado, bucket-history, import/export, and Google subtrees.
It does not construct raw SQL engines or direct secure-object adapters in command
handlers.

## S378-002 | FIXED | Broad containment paths now leave debug evidence

Profile-record display/readiness, profile import parsing, profile status projection,
and repair log tail failures now write debug breadcrumbs through the centralized logger
before rendering operator-safe diagnostics or localized refusals.

## S378-003 | PASS | Locale and error boundaries remain enrolled

User-facing refusals stay on `tr()` keys or registered `AeatError`/CLI boundary
exceptions. The patch added no locale keys, and the canonical locale audit passes via
`python -m aeat.locales audit`.

## S378-004 | PASS | Validation

- Focused `ruff check` passed for the config facade and relevant config/profile repair
  tests.
- Focused integration tests passed for config boundary, repair bootstrap exemption, and
  reset-state behavior.
- `python -m aeat.locales audit` passed.

Disposition: close `AFR-276`; continue with `AFR-277` for the Google-specific
remote-provider implementation.
