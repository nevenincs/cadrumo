---
tags:
  - '#audit'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:1afb69209220831f9f28dae4dc5675cc45ac73073c1d48421badf99f28a20057'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---
# `aeat-export-fragment-generator-authority` audit: `s83 m303 2022 orden authority`

## Scope

Reviewed the source-pinned 2022 annual Orden compiler, generated corpus and
manifest, Modelo 303 source/revision binding, explicit agricultural-crosswalk
refusal, Lorca authority envelope, and accompanying direct-behaviour tests.

## Findings

### s83 m303 2022 orden authority | high | Coordinated public-envelope provenance drift

The initial public envelope could be coordinated to a different parent source
and child Lorca/reference coordinate. The correction binds the 2022
HFP/1335/2021 source identity, digest, legal reference, revision, and record
design across the snapshot boundary. Real-envelope parent-and-child drift and
authority-removal probes now refuse.

### s83 m303 2022 orden authority | low | Brittle aggregate legal-reference tally

The fixed total was replaced with a source-grouped property: each unique
annual source carries every compiled axis exactly once, duplicate
same-source projections agree, and their union equals the legal map.

## Recommendations

No remaining S83 finding. Retain the explicit unavailable agricultural
crosswalk input until an official two-digit DP30302 crosswalk is acquired;
do not derive it from activity descriptions, raw keys, or rates.

Final review found no S83-owned correctness defect. The complete S83-focused
regression completed 115 passing tests; its nine failures occur before an S83
assertion when an unrelated shared invoice envelope deserializes
`retention_rate: None`. The direct Orden parser, generated-registry check,
static checks, and targeted aggregation-helper probes pass.
