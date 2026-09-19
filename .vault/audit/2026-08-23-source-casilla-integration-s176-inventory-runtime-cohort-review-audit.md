---
tags:
  - '#audit'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:ce2ccaa06d67e35bf90b17b7663865abbc2f58df6111c00324a24d0b2c373f17'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# `source-casilla-integration` audit: `source-casilla-integration audit: s176 inventory runtime cohort review`

## Scope

Independent review of template cohort completeness, activity ordering, sealed projection reuse, row identity alignment, encrypted repository behavior, failure atomicity, and confidentiality.

## Findings

### s176-inventory-runtime-cohort-review | high | resolved noncanonical activity identity escape

The inventory ledger initially admitted activity identifiers with surrounding whitespace or control characters, while the canonical row identity refused them during expansion. The owning ledger now rejects those identities with hidden input values, and the resolver retains an exact typed validation fallback so no partial cohort can escape.

### s176-inventory-runtime-cohort-review | high | resolved encrypted restoration proof gap

Early tests used only a repository spy. The final matrix exercises the real encrypted schema-v3 inventory repository for absence, two-activity success, retained conflict, and re-encrypted authority-coordinate corruption, alongside tamper, semantic mutation, order invariance, and value-free canary checks.

### s176-inventory-runtime-cohort-review | pass | final activity cohort is coherent

Exactly one template per operation expands over lexically ordered activities. Each activity appears once per operation at the same row index and shares one opaque identity and sealed projection fingerprint across the cohort. No scalar or cross-activity aggregate is emitted, and final review reported zero findings.

## Recommendations

Proceed with downstream inventory binding and persistence work using the typed aligned row cohort; do not reconstruct activity identity from row order or ordinary diagnostics.
