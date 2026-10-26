---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-10-03'
body_hash: 'sha256:5005edcac0d59a76dbadfafe38a5b2a8971acdbe73f9a3694c24e00f369a6cb2'
related: []
---

# `secure-storage-production-hardening` Error Registry Hygiene

## ERH-001 | FIXED | IVA wallet seed exceptions bypassed the AEAT error base

Root-help and core-error validation during the W12.P26 closeout surfaced that the
Modelo IVA wallet seed exception root still derived from built-in `Exception`.
The seed error now derives from the modelo error hierarchy and has explicit
central error-code entries for the base seed error, missing-taxpayer refusal, and
negative-amount refusal.

## ERH-002 | FIXED | Registry enforcement depended on prior test imports

The registry enforcement test walked the error-test package path when run in
isolation and could also observe intentionally unregistered test-only classes
created by sibling tests in the same process. The guard now imports production
`aeat` modules deterministically and excludes test-only subclasses from the
production registry invariant.

## Validation

- `uv run --no-sync ruff check ...`
- `uv run --no-sync pytest -q src/aeat/core/errors/tests`
- the historical check
- `uv run --no-sync python -m aeat.locales audit`

## Review

The `vaultspec-code-reviewer` review reported no findings for the scoped repair.
