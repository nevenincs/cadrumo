---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-26'
modified: '2026-07-17'
body_hash: 'sha256:7293494def399b0f52b4105a492c5e86be62a0d979f9104d8724ca8c908a1956'
step_id: 'S65'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-22-secure-storage-production-hardening-architecture-research]]'
  - '[[2026-05-26-secure-storage-tr-locale-error-message-audit]]'
---

# `secure-storage-production-hardening` `W10.P17.S65`

Audited secure-storage user-facing errors for locale-backed `tr()` rendering.

- Created: `.vault/audit/2026-05-26-secure-storage-tr-locale-error-message-audit.md`
- Created: `.vault/exec/2026-05-22-secure-storage-production-hardening/2026-05-26-secure-storage-production-hardening-W10-P17-S65.md`

## Description

The audit confirmed the codebase convention: `AeatError` rendering uses `translated_message` and registered `message_key` values through `tr(...)`. It also identified a secure-storage gap: literal `message` arguments on storage exceptions bypass locale rendering because the central error renderer returns `error.args[0]` before falling back to registry keys.

The audit binds remediation to W11 rows instead of performing ad hoc edits in the audit step. W11 owns conversion of operator-facing storage errors, exception-constructor alignment, exception observability, and settings-route wording cleanup.

## Tests

`uv run python -m aeat.locales audit` reported `ok` for all locale catalogs before this audit step.
