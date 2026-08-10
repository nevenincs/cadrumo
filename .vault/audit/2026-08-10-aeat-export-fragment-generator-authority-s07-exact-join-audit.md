---
tags:
  - '#audit'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:ff2e3b3c003abf322b6ae98ee552b10b158747fefe68bbd768ce8ba2db0148be'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---

# `aeat-export-fragment-generator-authority` audit: `s07 exact join`

## Scope

Review the S07 parser-to-semantic-map join against the accepted source-authority decision, with emphasis on source ordering, exact-anchor admission, and the hard removal of non-authoritative input surfaces.

## Findings

### derivative-input-guard | medium | The structural cutover guard omitted derivative inputs

The first independent review found that the red guard rejected known layout, approximate-match, and extracted-input names but did not reject the derivative input surface explicitly required by the accepted decision. A renamed derivative reader could therefore evade the intended guard.

### derivative-input-guard | medium | Resolved by expanding the structural prohibition set

The S07 module now contains no derivative, provenance, rendering, or export-loader surface, and the guard fails on each of those terms alongside layout, approximate-match, positional, fallback, and extracted-input names. The reviewer rechecked the exact scoped source and confirmed the finding closed. No critical or high finding was identified.

## Recommendations

- Retain the S07 structural guard whenever the join boundary changes; place later rendering and provenance behavior in their separately planned modules.
