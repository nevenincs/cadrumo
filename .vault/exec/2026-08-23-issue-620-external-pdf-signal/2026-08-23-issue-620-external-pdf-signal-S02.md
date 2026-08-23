---
tags:
  - '#exec'
  - '#issue-620-external-pdf-signal'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:a3327d29d73557e27b53d34ad71ea1665feffbabb0a3b58130315bf53cac913d'
step_id: 'S02'
related:
  - "[[2026-08-23-issue-620-external-pdf-signal-plan]]"
---

# Inventory and fingerprint the externally sourced Modelo 131 plain and fillable PDFs

## Scope

- `src/cadrumo/tests/fixtures/external_layout_candidates/131/`

## Description

Download the source-page plain and fillable candidates without transforming the bytes.

Fingerprint each payload and inspect its PDF version, page geometry, document information, encryption state, AcroForm shape, and empty-value state.

Record the source page, exact download URL, retrieval date, physical observations, identity-pattern scan, value observations, and evidential limitations in strict JSON sidecars.

Verify both exact download URLs still return the inventoried bytes.

## Outcome

The plain candidate is 141662 bytes with SHA-256 `816e33a3452e508a62bd363030901b8d54dea362cc7b3db2c0b58fcd7f992927`; the fillable candidate is 109408 bytes with SHA-256 `3c271a489d21556d8b69fce20a165e311ba85a1b9ef26632199bfa3d4eadbef4`.

Both candidates are one-page blank external layouts. The source-labeled plain candidate still has 19 top-level AcroForm fields; the fillable candidate has 66. Neither has a non-empty form value, and the bounded text scan found no populated NIF-like, IBAN-like, or email-like value.

The sidecars classify both payloads as third-party-hosted external layout candidates with unverified authority status. They record the PDFescape creator metadata as a physical observation, refuse to infer provenance from it, and refuse to infer populated-value placement from the blank layouts.

## Notes

The source page's `plain` and `fillable` labels are recorded only as candidate-kind labels. The presence of AcroForm fields in the plain candidate proves those labels cannot be treated as semantic classifications.

A Python standard-library fetch received HTTP 403 from the host. The byte-for-byte remote check therefore used `curl` against each exact recorded URL and passed for both candidates.
