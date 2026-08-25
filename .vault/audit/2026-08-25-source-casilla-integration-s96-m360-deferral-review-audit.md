---
tags:
  - '#audit'
  - '#source-casilla-integration'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:b0321bb09da9d3f5a13b30b1c55ed0033fff24007e0b6d19dc82d135fbd9f3d1'
related:
  - "[[2026-08-22-source-casilla-integration-W05-P16-S96]]"
---

# `source-casilla-integration` audit: `S96 M360 deferral review`

## Scope

Independent review of S96 in commit `f1d8f52b48` and the bounded Modelo 360 census predicate. The review compared the cited AEAT request and document-detail axes to the live row carrier, resolver-disposition mesh, census, and pending S97-S99 plan rows.

## Findings

### canonical-research-linkage | low | S96 execution Scope named the obsolete research locator

The plan, index, and canonical research record use `2026-08-22-source-casilla-integration-m360-row-source-grounding-research`, but the S96 record's Scope omitted the feature segment. The Scope has been corrected; no source contract changed.

### m360-deferral-predicate | low | The strengthened predicate is evidence-backed and remains bounded

AEAT's form guidance establishes a request country, year, and refund-period context plus invoice/import-document identity, issue date, base, VAT quota, deductible proportion, refund amount, currency, nature, and supplier identity/address. The live `RefundOperationObservation` has only the partial worksheet projection and a synthetic row identity; `REFUND_OPERATION` remains deferred and no route owner claims it. The dirty census predicate therefore correctly retains `ingress_blocked` and makes S97-S99 the reopening proof program. A no-mock test now binds the condition, absence of resolver and connected lifecycle, and expiry refusal.

## Recommendations

Do not implement S97 until one secure owner has been independently designed to retain the complete official request and document record with immutable identity and fingerprint. Keep S98 and S99 contingent on that owner and on a supported repeated-record export route.
