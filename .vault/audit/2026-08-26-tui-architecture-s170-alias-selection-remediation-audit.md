---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:88daa1f621dab5a1efa2c150ae55f4adba3f1fd263ffdde84bd6d5d6472d9dd8'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
  - "[[2026-08-26-tui-architecture-s170-high-findings-remediation-audit]]"
  - "[[2026-08-11-tui-architecture-W03-P20-S170]]"
---
<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace tui-architecture with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

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

