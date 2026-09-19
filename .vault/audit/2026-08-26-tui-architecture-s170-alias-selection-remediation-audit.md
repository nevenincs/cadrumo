---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:b3172a77b178de4f8d119835d548f6257d585b6da7f966fa5ba74f6fb4928549'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
  - "[[2026-08-26-tui-architecture-s170-high-findings-remediation-audit]]"
---

# `tui-architecture` audit: `S170 alias and selection remediation`

## Scope

Corrective record for the second independent S170 review. That review retained
a FAIL because local alias chains and `.items()` tuple targets bypassed the
natural selector detector, the whole canonical file was exempt rather than its
one defining function, and coordinate-only projection loops produced false
positives. The same semantic gaps existed in resident-result classification.
This audit records remediation evidence without changing the S170 plan state.

## Findings

### local-alias-dataflow | high | Wrapper and catalogue aliases resolve transitively

Keyword-source analysis now follows local name chains, so
`loaded=repo.load(); catalogue=loaded` reaches the repository read. Natural
scan analysis likewise resolves `units=catalogue` before recognizing
`units.values()` or `units.items()`. Exact mutants require the original
violation kinds for both bypasses.

### tuple-target-selection | high | Items iteration identifies the selected tuple member

The reusable natural-scan rule supports both `values` and `items`. Candidate
names are derived from the complete loop target, so a `(key, unit)` target is
recognized when `unit` supplies the natural-coordinate comparisons. The RAG
classifier consumes the same reusable source predicate rather than maintaining
a parallel syntax detector.

### exact-canonical-exemption | high | Only the canonical defining function is exempt

Natural-scan rules declare exact exempt function names. The canonical module is
still inspected, and an exact mutant containing the legitimate canonical
selector plus a second selector requires the additional function to report
`parallel natural catalogue scan`.

### selection-semantics | high | Coordinate projections no longer count as selection authority

A natural scan now requires at least the configured number of candidate
coordinates to participate in comparison expressions. Merely reading
`modelo`, `filing_year`, and `period` while yielding or projecting rows does not
report a selector. Static and RAG negative mutants prove the distinction;
positive alias and tuple-target mutants remain rejected.

### focused-evidence | low | Scanner, fixed-point, classifier, and resident proofs pass

Ruff passed. The fixed-point, public cutover, and reusable scanner suites
completed with 43 passing tests in 101.80 seconds. The direct resident-service
S170 proof passed at explicit port `8766` in 2.96 seconds. These are remediation
evidence for another independent review, not a self-issued PASS.

## Recommendations

Keep `W03.P20.S170` unchecked. Commit only the reusable scanner, declarative
fixed-point and RAG tests, and this audit. A subsequent independent Sol-medium
review must replay every positive bypass and both projection-loop negative
controls before recommending any lifecycle transition.
