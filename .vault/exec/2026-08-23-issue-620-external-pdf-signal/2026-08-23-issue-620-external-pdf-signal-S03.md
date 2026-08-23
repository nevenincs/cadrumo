---
tags:
  - '#exec'
  - '#issue-620-external-pdf-signal'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:b6b0c9f6ac2fa2d1f1b0e080d4b9ac0f8704b1da61ae309cf3e88b110f522cf9'
step_id: 'S03'
related:
  - "[[2026-08-23-issue-620-external-pdf-signal-plan]]"
---

# Inventory and fingerprint the externally sourced Modelo 303 plain and fillable PDFs

## Scope

- `src/cadrumo/tests/fixtures/external_layout_candidates/303/`

## Description

Download the source-page plain and fillable candidates without transforming the bytes.

Fingerprint each payload and inspect its PDF version, page geometry, document information, encryption state, AcroForm shape, and empty-value state.

Record the source page, exact download URL, retrieval date, physical observations, identity-pattern scan, value observations, and evidential limitations in strict JSON sidecars.

Verify both exact download URLs still return the inventoried bytes.

## Outcome

The plain candidate is 79291 bytes with SHA-256 `bd99c3b277060bdb8577859540bb7c4171aea223f74de9a86302f6da3db66957`; the fillable candidate is 205720 bytes with SHA-256 `a0d613fcfbd59b57f071f92ecc6a745fd2a428d5676a00de43e8bb184a44036c`.

Both candidates are three-page blank external layouts. The plain candidate has no AcroForm fields; the fillable candidate has 130 top-level fields and no non-empty value. The bounded text scan found no populated NIF-like, IBAN-like, or email-like value.

The sidecars classify both payloads as third-party-hosted external layout candidates with unverified authority status. They record the third-party editor and producer metadata as physical observations, refuse to infer provenance from them, and refuse to infer populated-value placement from the blank layouts.

## Notes

The source page's `plain` and `fillable` labels are recorded only as candidate-kind labels; they are not semantic or provenance claims.

A Python standard-library fetch received HTTP 403 from the host. The byte-for-byte remote check therefore used `curl` against each exact recorded URL and passed for both candidates.
