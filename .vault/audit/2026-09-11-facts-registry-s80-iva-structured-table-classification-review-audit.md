---
tags:
  - '#audit'
  - '#facts-registry'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:ffdacd0358c92a9def163afa318749741815b65f6635e24f7ed37c50f0970f69'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---
# `facts-registry` audit: `S80 IVA structured-table classification review`

## Scope

Read-only review of W04.P15.S80 against the approved plan, the adapted-family-normalization reference, the five remaining IVA registry tables, their direct readers, and the S80 classification contract.

## Findings

### classification-census | medium | Resolved: independent source census now binds every listed table

The remediation directly parses all five IVA tables, asserts each table name and exact row count, and binds every parsed row sequence to a canonical semantic digest. It also demonstrates that an isolated same-count mutation of an operative catalogue field changes the digest. This closes the prior gap where a stale ledger count could agree with a duplicate test constant. The legal-table classifications remain conservative: generic facts cannot retain their citation quotation/grounding/window, establishing-reference, exempt-row, postal-prefix, or three-way territorial-disposition semantics. The country vocabulary remains separately classified as AEAT/Facturae technical interoperability authority.

## Recommendations

Final verdict: CLEAR. Retain the four legal tables until their lossless typed fact families and authority projections are implemented; retain the country vocabulary as canonical technical data. No IVA source deletion is authorized by S80.
