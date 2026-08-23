---
tags:
  - '#exec'
  - '#issue-620-external-pdf-signal'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:b0bdd388579d61181947a3ee620ae857d24bcdb36840fdbaf6d4c0d69c8b9efa'
step_id: 'S05'
related:
  - "[[2026-08-23-issue-620-external-pdf-signal-plan]]"
---

# Inventory and fingerprint the externally sourced Modelo 349 plain and fillable PDFs

## Scope

- `src/cadrumo/tests/fixtures/external_layout_candidates/349/`

## Description

- Preserve the plain and fillable Modelo 349 downloads byte-for-byte.
- Record the source page, versioned download locators, retrieval date, SHA-256 digests and byte lengths.
- Measure PDF version, page geometry, encryption, AcroForm shape, document metadata and text-layer identity-pattern observations.
- Classify both files as unverified third-party-hosted external layout candidates.

## Outcome

The plain candidate is a two-page unencrypted PDF with no AcroForm, digest `dc77e58a8eb5b24fb5f7dccf65c51dcfc495debd0b053e1d091c9fca8e6abbed`, and producer observation `iLovePDF`. The fillable candidate is a two-page unencrypted PDF with 82 empty top-level AcroForm fields, digest `0457d6a646e2af9ef95ec5be59e3546f31ecd164f9a96899cbe15e26b0d2c539`, and producer observation `3.0.30 (5.1.14)`.

Both text layers contain the printed placeholder justificante number `1234567890` and no NIF-like, IBAN-like or email-like match. Focused revalidation confirmed both sidecar digests, sizes, page counts, encryption state, header versions and recorded text-layer counts against the preserved bytes.

## Notes

The files were downloaded from FiscalBot, not from an authenticated AEAT channel. AEAT-labelled metadata and branding are recorded physical observations only and do not establish authority. The blank layouts cannot ground populated-value placement. Redistribution rights remain unadjudicated under the governing ADR constraint.
