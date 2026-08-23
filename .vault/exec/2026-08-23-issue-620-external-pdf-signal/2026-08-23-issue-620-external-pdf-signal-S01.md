---
tags:
  - '#exec'
  - '#issue-620-external-pdf-signal'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:13a20b2bddf90bf6e73bd2a41de03b1b240cd00f9f592d6b8341290055148a7e'
step_id: 'S01'
related:
  - "[[2026-08-23-issue-620-external-pdf-signal-plan]]"
---

# Inventory and fingerprint the externally sourced Modelo 130 plain and fillable PDFs

## Scope

- `src/cadrumo/tests/fixtures/external_layout_candidates/130/`

## Description

Download the source-page plain and fillable candidates without transforming the bytes.

Fingerprint each payload and inspect its PDF version, page geometry, document information, encryption state, AcroForm shape, and empty-value state.

Record the source page, exact download URL, retrieval date, physical observations, identity-pattern scan, value observations, and evidential limitations in strict JSON sidecars.

Verify both exact download URLs still return the inventoried bytes.

## Outcome

The plain candidate is 186217 bytes with SHA-256 `bfe5fb7d63a07660f5b36b63f702b522efa7b21ffa66e3c8bc7ffd17c13e824f`; the fillable candidate is 155146 bytes with SHA-256 `cb2440c04f499005a5bb93231b2072d2b585d40283a60eedce7d73d1efed1379`.

Both candidates are one-page blank external layouts. The plain candidate has no AcroForm fields; the fillable candidate has 31 top-level fields and no non-empty value. The bounded text scan found no populated NIF-like, IBAN-like, or email-like value.

The sidecars classify both payloads as third-party-hosted external layout candidates with unverified authority status. They explicitly refuse to treat hosting, branding, or document metadata as AEAT provenance and refuse to infer populated-value placement from the blank layouts.

## Notes

The source page's `plain` and `fillable` labels are recorded only as candidate-kind labels; they are not semantic or provenance claims.

A Python standard-library fetch received HTTP 403 from the host. The byte-for-byte remote check therefore used `curl` against each exact recorded URL and passed for both candidates.
