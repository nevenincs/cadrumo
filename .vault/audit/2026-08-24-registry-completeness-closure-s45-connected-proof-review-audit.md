---
tags:
  - '#audit'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:8ed68c6d558f754f88ad867a76ea5178433480ebc00a0e50152144f17c9ae822'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
  - "[[2026-08-24-registry-completeness-closure-adr]]"
---

# `registry-completeness-closure` audit: `S45 connected proof revalidation review`

## Scope

Independent review of commit `a4bd65ed1c` against the accepted closure decision and
S45's requirement to revalidate connected census claims at report composition time.
The review covered report-time authority use, default-absent authority behaviour,
encrypted calculation-revision persistence, executable-evidence drift, refusal
taxonomy, and the focused unit and integration gates.

## Findings

### proof-failure-taxonomy | medium | Missing proof is reported as conflicting evidence

`_connected_proof_failures` retains only rendered validation prose, and
`_refused_connected_claim_limb` in
`src/cadrumo/application/registry/_source_connectivity_coverage.py:296` infers the
refusal reason by searching that prose for the word `changed`. The core validator at
`src/cadrumo/core/source_connectivity.py:481` deliberately emits the single message
`absent or changed` for both a missing executable-evidence file and a digest mismatch.
Consequently both conditions become `conflicting_evidence`, even though S45 requires
proof loss to remain distinguishable from digest mismatch. The new composer regression
covers changed bytes only, so deletion at this boundary is not proven and the
misclassification remains invisible.

## Recommendations

- Replace prose substring inference with a structured proof-failure cause that maps an
  absent authority or absent executable artifact to `missing_evidence`, and a verified
  digest divergence to `conflicting_evidence`.
- Add real encrypted-repository composer regressions for both evidence deletion and
  changed bytes, asserting the exact refusal reason and actionable disposition.
- Keep the focused evidence explicit: Ruff passed; all five source-coverage unit tests
  passed; the S45 encrypted-repository digest-drift integration regression passed. A
  separately selected pre-existing raw-lineage deletion test remains red because it
  expects `ValidationError` after the repository wraps invalid payloads as
  `CalculationRevisionPersistenceError`; that is not caused by the S45 diff and is not
  used as proof of this finding.
