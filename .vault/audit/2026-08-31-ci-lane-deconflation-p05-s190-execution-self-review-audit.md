---
tags:
  - '#audit'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:c0dd13218f2b65f5331199490ee3279919c90ca1b299dc2b56340a33a6969210'
related:
  - "[[2026-08-05-ci-lane-deconflation-P05-S190]]"
---

# `ci-lane-deconflation` audit: `p05 s190 execution self review`

## Scope

Self-review of the P05.S190 execution record, its isolated source/test staging manifest, the extracted record-design sibling family, and the stated verification evidence before independent review.

## Findings

No CRITICAL or HIGH finding remains in the reviewed current source surface.

### source-staging-isolation | medium | Resource relocation was initially co-located with the S190 import moves

Eleven files contained both the record-design move and an unrelated `core.resources` relocation. The execution manifest requires a temporary index and retains the resource hunk outside S190; the reviewed source commit therefore contains only the private-import moves in those files.

### constant-ownership-remediation | low | The pre-receipt direct-consumer risk is resolved

The removed primary-module constant originally left `dev.registry.pipeline._render_profile` with a stale direct import and was duplicated during the split. The current source has one owner in `record_design_pdf_rows`, the direct consumer imports that owner, and the runtime import probe passes without a cycle.

### verification-scope | low | The focused receipt is not a substitute for a broad parser receipt

The recorded pytest evidence is exactly the supplied two-file 13-pass focused run. A broader/core `test_record_design.py` attempt has no completed receipt, so neither this audit nor the execution record claims it passed. The global size audit also remains red solely on its reported out-of-scope backlog; no changed record-design production subject is named.

## Recommendations

- Preserve the isolated temporary-index manifest when reviewing or committing S190; do not absorb the eleven peer resource-relocation hunks.
- Independently review the committed source and this receipt, including the canonical constant owner, runtime import graph, and stated test limitation.
