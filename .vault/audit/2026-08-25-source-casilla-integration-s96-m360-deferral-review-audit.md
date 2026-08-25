---
tags:
  - '#audit'
  - '#source-casilla-integration'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:1e03f310eae78fde0192889b1c863b5774170c0cb1c224ccd57d53401feb7b8f'
related:
  - "[[2026-08-22-source-casilla-integration-W05-P16-S96]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace source-casilla-integration with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

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
