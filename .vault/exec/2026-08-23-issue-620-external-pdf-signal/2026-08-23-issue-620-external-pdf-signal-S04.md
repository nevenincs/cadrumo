---
tags:
  - '#exec'
  - '#issue-620-external-pdf-signal'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:72cbe01ac6e58f756e55d8bcfc3bbea7656bafc936e8ba8e8cf48442335a75c1'
step_id: 'S04'
related:
  - "[[2026-08-23-issue-620-external-pdf-signal-plan]]"
---

# Inventory and fingerprint the externally sourced Modelo 036 plain and fillable PDFs

## Scope

- `src/cadrumo/tests/fixtures/external_layout_candidates/036/`

## Description

- Preserve the plain and fillable Modelo 036 downloads byte-for-byte.
- Record the source page, versioned download locators, retrieval date, SHA-256 digests and byte lengths.
- Measure PDF version, page geometry, encryption, AcroForm shape, document metadata and text-layer identity-pattern observations.
- Classify both files as unverified third-party-hosted external layout candidates.

## Outcome

The plain candidate is a four-page unencrypted PDF with no AcroForm, digest `27b887171666bc8423cabaa557b2f3ba040079ab73428f9f7f956f9cd7fc519a`, and producer observation `iLovePDF`. The fillable candidate is a four-page unencrypted PDF with 330 empty top-level AcroForm fields, digest `5fdcc9ca1bc770c71286a94db3190267bcd2d86224737a56f25382526ed14b82`, and producer observation `3.0.31 (5.1.15)`.

Both text layers contain the printed placeholder justificante number `1234567890` and no NIF-like, IBAN-like or email-like match. Focused revalidation confirmed both sidecar digests, sizes, page counts, encryption state, header versions and recorded text-layer counts against the preserved bytes.

## Notes

The files were downloaded from FiscalBot, not from an authenticated AEAT channel. AEAT-labelled metadata and branding are recorded physical observations only and do not establish authority. The blank layouts cannot ground populated-value placement. Redistribution rights remain unadjudicated under the governing ADR constraint.
