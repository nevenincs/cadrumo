---
tags:
  - '#audit'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:140fe7c4bd020f942faea01f8b2aa3b0b6512c54167f17b7514a1664e5831de0'
related:
  - "[[2026-08-05-ci-lane-deconflation-P05-S182]]"
---

# `ci-lane-deconflation` audit: `p05 s182 execution self review`

## Scope

Independent self-review of the P05.S182 execution record against source provenance `4ced237398edb70bd54a0eef6550fda705dc0d70`, its four-path manifest and immutable physical/raw line comparison, supplied focused receipts, the mixed integration receipt, size-budget-policy boundary, and isolated vault-artifact scope.

## Findings

### p05-s182-execution-self-review | low | Integration receipt is non-green but unrelated to the split

The exact receipt is `1 passed, 2 failed, 4 deselected in 293.23s`. Both failures concern shared `corpus_catalogue` `applies_across` behavior rather than the `authority.py` split, so the execution record accurately retains them as a limitation and makes no green integration claim.

### p05-s182-execution-self-review | high | Count labeling corrected

An earlier correction inaccurately called nonblank PowerShell line counts committed raw counts. The corrected record now carries only the immutable physical/raw comparison for source commit `4ced237398edb70bd54a0eef6550fda705dc0d70`: 1365 parent `authority.py` lines, 1142 committed `authority.py` lines, and a new 253-line sibling. It also completes the commit manifest with both direct-consumer import repoints.

### p05-s182-execution-self-review | low | No baseline or threshold mutation

Neither the source commit nor the corrected execution record changes a size-budget baseline or threshold.

## Recommendations

Keep the two shared `corpus_catalogue` failures separately owned and rerun the integration selection once that shared surface is stable; do not use this record as a green integration receipt. Keep the peer filing-relocation portions of the two mixed `dev/registry` paths outside the S182 source-commit attribution.
