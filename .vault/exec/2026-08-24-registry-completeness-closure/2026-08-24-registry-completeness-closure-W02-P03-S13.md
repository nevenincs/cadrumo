---
tags:
  - '#exec'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:fa3958af6f199221039cb389f1fae2368cc52958e6dd3b3bfd7a12aad5ab7a9f'
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
metadata claims the 2024 PDF from 2002. The temporal/export owners must correct
that boundary before any fileability work is reconsidered.

## Notes

- `test_cited_design_field_bounds_are_self_consistent.py` passed: 3 tests.
- The aggregate filing-capability worklist assertion is intentionally red with
  fourteen current refusal rows; its Modelo 038 row reports the expected design
  extraction blocker. No production file changed.
