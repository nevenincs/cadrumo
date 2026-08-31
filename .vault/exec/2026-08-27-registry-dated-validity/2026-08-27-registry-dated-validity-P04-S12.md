---
tags:
  - '#exec'
  - '#registry-dated-validity'
date: '2026-08-27'
modified: '2026-08-27'
body_schema: 'body-v2'
body_hash: 'sha256:9a82b99dc5b27b88803b5f0198b46624da49f7711d86aed6c281ca64b6287ae3'
step_id: 'S12'
related:
  - "[[2026-08-27-registry-dated-validity-plan]]"
---

# Obtain the official RETA cuota maxima por contingencias comunes for every supported filing year from AEAT and BOE primary sources, cross-checking each figure against a second official source and verifying that AEAT's own published method reproduces every published year before using it to derive the one year AEAT has not yet published

## Scope

- `external official sources`
- `recorded in the feature audit`

## Changes

- `verify:` `AEAT Manual practico Renta 2022-2025 and BOE Ordenes PJC/178/2025, PJC/297/2026` -> `pass`

## Notes

No file changed: this row obtained evidence. The five figures and their
provenance are recorded in the feature audit. Two independent official sources
agree on 2025 (the Manual's printed figure and the orden's base and tipo), and
AEAT's own printed method reproduces all four published years to the cent, which
is what licenses deriving 2026 from the orden alone. A first web search returned
two different 2025 base figures from secondary summaries; both were discarded in
favour of the primary orden text.
