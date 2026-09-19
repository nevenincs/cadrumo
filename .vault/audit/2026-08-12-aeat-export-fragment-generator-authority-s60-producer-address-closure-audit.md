---
tags:
  - '#audit'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:7f149c89d98f569f1c68b2471394bfaa6dcf3ae940d9274875ed71dca20166a3'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
  - "[[2026-06-13-m303-form-vs-semantic-casilla-dual-keying-adr]]"
---
# `aeat-export-fragment-generator-authority` audit: `S60 Producer and Projection Address Closure Audit`

## Scope

Audited the remaining S19-exposed Modelo 303 producer and projection-address gaps: taxpayer tax identity and DP30302 simplified-module addressing against the annual Orden snapshot.

## Findings

### taxpayer-tax-id-owner | low | taxpayer identity is distinct from presenter identity

The closed `FilingProducerKey` vocabulary now includes `taxpayer.tax_id`, resolved solely from the immutable filing snapshot's taxpayer identity. A real behavior test supplies distinct taxpayer and presenter identifiers and proves neither can fall back to the other.

### annual-orden-module-address | low | DP30302 selects modules by exact ordinal

The S57 projection contract already requires bounded `module_order` without a default and refuses the retired `module_identity` shape. A real 2026 annual-Orden snapshot test proves ordinal two and three select the corresponding validated annual-Orden module values. Formal review approved S60 with zero unresolved critical, high, or medium findings.

## Recommendations

Keep taxpayer and presenter identities separate and preserve annual-Orden ordinal addressing. Any alias, fallback, raw mapping, activity-specific module identity, or inferred order is a hard regression.
