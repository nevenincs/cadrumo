---
tags:
  - '#exec'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:49f112440e2874ba109ff62b882750bc6c0b52bd6d27049b58530e996678017a'
step_id: 'S13'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
---
# Adjudicate Modelo 038 revision 2002-y-siguientes design extraction trust and fileability

## Scope

- `.vault/reference/`

## Description

- Re-fetch AEAT's record-design index, Modelo 038 filing guidance, and the two
  primary BOE authorities.
- Compare the current official source with the hash-pinned registry source,
  extraction output, source-era metadata, and refusal tests.
- Record the supported inspection boundary, export-owner disposition, and exact
  conditions that could reopen fileability.

## Outcome

Modelo 038 remains non-fileable. AEAT publishes an active fichero route and a
current official design, but the bundled visual design does not yield trustworthy
coordinates in the shipped extraction path; no export layout may cite it. The
revision remains applicability-grade and inspection-only.

The evidence also exposes a separate historical-scope defect: BOE-A-2024-13049
limits the IRUS change to the June 2024 declaration, while the current source
metadata claims the 2024 PDF from 2002. The later independent review enrolled
the exact routes: `registry-temporal-coverage` `W02.P05.S43` owns the validated
pre-June source-era correction, and `aeat-export-fragment-generator-authority`
`W04.P07.S96` owns trusted layout acquisition after that correction. Neither route
authorizes filing until its independent acceptance conditions close.

## Notes

- `test_cited_design_field_bounds_are_self_consistent.py` passed: 3 tests.
- The aggregate filing-capability worklist assertion is intentionally red with
  fourteen current refusal rows; its Modelo 038 row reports the expected design
  extraction blocker. No production file changed.
