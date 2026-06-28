---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-05-secure-storage-production-hardening-W12-P26-S377]]'
---

# `secure-storage-production-hardening` `W12.P26.S377` Review

## S377-001 | PASS | CLI common is not manifest discovery

`_common.py` renders CLI output, normalizes period/date inputs, translates CLI helper
messages, and creates typed domain/application repositories. It does not parse bucket
manifests, inspect raw SQL routes, read environment variables, or materialize storage
runtime adapters directly.

## S377-002 | FIXED | Aggregation invoice reads now share the resolved bucket

The Renta aggregation helper already resolved an active bucket for aggregation, but the
invoice repository was previously constructed with the implicit active-profile default.
The helper now carries the resolved bucket id into the invoice repository so transaction
and invoice input resolution remain pinned to the same profile bucket.

## S377-003 | PASS | Refusals remain localized and typed

No-active-profile paths continue to raise or emit translated values through `tr()` keys
and `CliRefusedBoundaryError`. Input parsing errors remain Click/Typer input refusals
with locale-sourced messages, and repository/runtime failures continue to surface from
the core `AeatError` hierarchy.

## S377-004 | PASS | Validation

- `ruff check` passed for `_common.py` and focused CLI/aggregation tests.
- Focused common and Renta aggregation pytest suites passed.
- Integration backend-boundary and common helper tests passed with `-m integration`.
- `python -m aeat.locales audit` passed.

Disposition: close `AFR-275`; keep later CLI configuration rows focused on remote
provider mirrors, profile lifecycle storage, and repair surfaces.
