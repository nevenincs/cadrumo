---
tags:
  - '#exec'
  - '#declaracion-real-render-verification'
date: '2026-07-27'
modified: '2026-07-27'
body_hash: 'sha256:5db4fbb7ea0caa18502adc4aabe482ccab45c4b3d175f226c6cffb2eb1a555c0'
step_id: 'S16'
related:
  - "[[2026-07-26-declaracion-real-render-verification-plan]]"
---

# Scope the M100 parser follow-on ADR covering the shared pdfplumber primitive, the estate-wide named_label capture contract, and the M100 floor under D2

## Scope

- `.vault/adr`

## Description

## Outcome

The record exists, is accepted, and takes no decision. It scopes three coupled questions instead of presenting one fix: whether the shared inbound-PDF primitive may change its word segmentation, whether the estate-wide named_label capture contract may change, and what coverage floor Modelo 100 could carry afterwards.

Both blocking measurements were run rather than left for a future author. The shared primitive has three production consumers. The declaracion adapter was already measured, with only Modelo 100 moving. The borrador corpus turned out to be wholly generated, so its half is undecidable rather than clean. The ledger evidence layer is not byte-identical: the one genuinely external document in its corpus changes line grouping, and that path parses invoice amounts by label-anchored regex, which is the same mechanism class this campaign exists to repair.

So the first question is answered no for the prototyped mechanism, and reopened in a narrower and better-posed form: find a mechanism that leaves the ledger path untouched, or scope the change to the declaracion entry point rather than the shared primitive.

The record also carries the handover evidence inline so the next author re-derives nothing: the three failing bbox offsets with coordinates, the prototype's nineteen of twenty-one with zero fabrications, and why size-aware segmentation alone makes Modelo 100 refuse every real render rather than fixing it.

## Notes
