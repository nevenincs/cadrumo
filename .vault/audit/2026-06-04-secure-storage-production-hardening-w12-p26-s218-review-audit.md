---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-W12-P26-S218]]'
---

# `secure-storage-production-hardening` `W12.P26.S218` Review

## S218-001 | FIXED | Source resolver now binds the repository to the context bucket

`InvoiceCatalogueSourceResolver` previously built a default
`InvoiceCatalogueRepository` without passing the calculation context bucket,
which delegated bucket choice to the ambient active profile. The default path
now passes `context.bucket_id`, matching the source-mesh contract that the
calculation context owns bucket selection.

## S218-002 | PASS | Runtime mismatch fails closed

The new two-bucket runtime test exercises a primary active profile with a
secondary calculation context bucket. The hardened resolver attempts to build
the repository for the secondary bucket and receives the storage runtime
mismatch refusal. This is the desired adverse-environment behavior; it avoids
silently reading the wrong encrypted catalogue and emitting an empty resolution.

## S218-003 | PASS | Validation

- `uv run --no-sync ruff check src/aeat/application/invoices/_source_resolver.py src/aeat/application/invoices/test_source_resolver.py` passed.
- `uv run --no-sync pytest -q src/aeat/application/invoices/test_source_resolver.py` passed.
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit` passed.

Reviewer note: no critical, high, medium, or low findings remain for S218.

Disposition: close `AFR-116` as `runtime-default`.
