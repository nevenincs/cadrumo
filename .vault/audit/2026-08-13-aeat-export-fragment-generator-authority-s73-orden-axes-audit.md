---
tags:
  - '#audit'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-13'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:0e81fe6142e78f4d07218b735340226d852e6fad9f7987bfc99eee98404ecf64'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---

# `aeat-export-fragment-generator-authority` audit: `S73 annual Orden regulatory axes code review`

## Scope

Independent review of the one annual-Orden parser, typed source/projection authority, bundled source corpus and manifest, annual-Orden split, filing validation/projection refusal boundary, and generated API surface for S73.

## Findings

### agricultural-crosswalk-refusal | medium | The unresolved agricultural crosswalk never reaches the filing-row refusal boundary

`AutoridadAgricolaOrdenAnualNoResuelta` carries the intended status and refusal token, but it is only stored on the annual Orden projection and snapshot. `validate_regimen_simplificado_rows` still receives only `orden.activities`, which contains only ANEXO II non-agricultural rows, and never consumes `agricultural_authority`; an agricultural filing row therefore fails later as merely absent from the annual Orden rather than with the declared official-crosswalk refusal. Wire the canonical unresolved authority into that validation/projection boundary and add a real agricultural-row test asserting the exact refusal token, with no inferred or defaulted code mapping.

## Recommendations

The finding is resolved in this change: the required unresolved agricultural authority now reaches both filing-row validation and DP30302 projection, where any agricultural row raises its declared `annual_orden_does_not_publish_dp30302_two_digit_agricultural_crosswalk` token before activity selection. The focused test uses the resolved bundled 2026 authority and does not fabricate a crosswalk.
