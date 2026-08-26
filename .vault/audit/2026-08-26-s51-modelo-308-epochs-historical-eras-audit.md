---
tags:
  - '#audit'
  - '#s51-modelo-308-epochs'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:542f0364920e180f97f766485b9beb6b1d29b64b3a351724dad983d9656f8d53'
related:
  - "[[2026-08-14-registry-temporal-coverage-plan]]"
---

# `s51-modelo-308-epochs` audit: `Modelo 308 historical epochs`

## Scope

Independent review of the Modelo 308 portions of groundwork commits `63135011cc` and `34285f97b8`, the committed epoch split, and the subsequent Modelo 308 consolidation `d18e4353cb8`. Reviewed the governing temporal decisions and S51 execution record; the four official sources, legal authority, revision windows, section artifacts, application links, schedules, bindings, exports, locale migration, and focused tests. The source hashes and byte counts match, all four eras and their measured geometry are exact, historical eras remain below filing authority without layouts, and the shared IVA edit does not touch Modelo 309. Result: FAIL because of one High finding. The separate M165 source gap and M200 concurrent deadline state are outside this review.

## Findings

### Modelo 308 historical epochs | high | The July-2011 form amendment is absent from `orden_aplicabilidad`

The legal catalogue correctly separates `orden-eha-1033-2011:articulo-unico`, which substitutes the Modelo 308 annex, from `orden-eha-1033-2011:disposicion-final-unica`, which makes it effective on 1 July 2011. The `2011-julio-2015` revision includes the former only in its broad legal references, while its `orden_aplicabilidad` declares the original approval article and the effective-date provision. This field must identify the ministerial Orden entries that approve or amend the form for the claimed window, so the actual amendment is missing from the authoritative applicability list. The focused legal-boundary test repeats the omission by asserting only the effective-date provision.

### Modelo 308 historical epochs | medium | Undated 2011 resolution is correct but not regression-proved

An undated `AD-HOC` request for 2011 currently raises `AmbiguousRevisionSelectionError`, correctly refusing to choose between the January-to-June and July-to-December eras. The focused test proves date-specific selection and an overlapping-date mutation, but never locks down the normal no-date refusal. A later resolver change could silently select an era for the undated request without failing either existing sub-year assertion.

Remediation evidence (2026-08-26): the July 2011 revision's
`orden_aplicabilidad` now names the approval article, the annex-substitution
amendment, and the effective-date provision. The focused legal-boundary test
asserts that exact authority set and both anchored legal records. The focused
selector test now explicitly refuses an undated 2011 `AD-HOC` request while
retaining the existing 30 June and 1 July explicit selections.

## Recommendations

- Add `orden-eha-1033-2011:articulo-unico` to the July revision's `orden_aplicabilidad` alongside the approval and effective-date authorities, and assert that complete authority set in the focused legal-boundary test.

- Add a focused no-date 2011 selector assertion that requires `AmbiguousRevisionSelectionError`; retain generic temporal resolution rather than adding a Modelo 308 selector.

## Closure

Re-review of `710f998da1`: PASS. The former High is remediated by the exact applicability tuple containing the approval article, `orden-eha-1033-2011:articulo-unico`, and the effective-date provision; both distinct BOE anchors remain tested. The former Medium is remediated by an explicit undated-2011 refusal assertion, while the June and July boundary selections and the overlap mutation remain independent behavioral checks. The focused Modelo 308 registry, record-design, and lint gates pass. No unresolved Critical, High, or Medium finding remains.
