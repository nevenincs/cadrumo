---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:95fada6137af8f69978d67aa925a17d63e1ec9352805d441193e24a6d0719d97'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
  - "[[2026-08-26-tui-architecture-s170-final-follow-up-review-audit]]"
---

# `tui-architecture` audit: `S170 high findings remediation`

## Scope

Corrective record for the two HIGH findings returned by the independent
Sol-medium S170 review at snapshot `bac0cb6db023`. The review reproduced four
static scanner false negatives and one resident-result classifier false
negative. This remediation extends the reusable scanner and declarative gates;
it does not change the S170 plan state or assert a final PASS.

## Findings

### nested-wrapper-dataflow | high | All reproduced repository-owning wrapper shapes now report the exact violation

The scanner now discovers function and class definitions nested beneath
control-flow statements without absorbing their bodies into the parent scope.
Wrapper analysis considers canonical selector calls throughout the owned
function scope rather than only a direct return call. Keyword-source dataflow
accepts both an inline `catalogue=repo.load()` call and a name whose local
assignment is `repo.load()` or `repo.load_revisioned()`. Exact mutants cover
inline loading, assigned selector result followed by return, and the same
two-step wrapper nested beneath control flow.

### standalone-natural-scan | high | A declarative semantic rule detects substitutable catalogue scans

`SubstitutableNaturalScanRule` declares collection names, iteration methods,
natural-coordinate names, and the minimum coordinate count. The scanner
rejects a function iterating `catalogue.values()` whose candidate is matched on
at least two of `modelo`, `filing_year`, and `period`, even when the canonical
selector is never called. The authority-owner rule applies to production and
tooling definitions while test fixtures remain part of the complete tracked
inventory for import, export, retired-text, and binding checks; synthetic
mutants are evaluated separately without an allowlisted path.

### rag-natural-owner | high | Mixed canonical and standalone natural-scan search results are rejected

The pure resident-result classifier now recognizes a production snippet that
iterates `.values()` and compares at least two natural coordinates as a
parallel owner. Its mixed-response mutant contains the canonical result and a
standalone natural selector and requires both production parallel paths to be
reported. The direct resident query continues to require the exact canonical
owner and an empty parallel-owner set.

### remediation-evidence | low | Focused static and resident proofs pass after the correction

Ruff passed for the scanner and both S170 test modules. The complete pair of
declarative fixed-point gates completed with 13 passing tests in 119.48
seconds. The direct resident-service S170 proof passed at explicit port `8766`
in 3.15 seconds. These results are implementation evidence only; an independent
review must reproduce the former false negatives before issuing a disposition.

## Recommendations

Keep `W03.P20.S170` unchecked. Commit the scanner, declarative fixed-point
mutants, resident classifier mutant, and this audit with explicit paths. Then
request a new independent Sol-medium review that replays every previously
reproduced false negative and verifies the complete tracked-live gate. Only
that reviewer may recommend a lifecycle transition.
