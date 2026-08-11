---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:0934afff5c91e96754a5faa0ab571f8c0d2a31203e7228d6cb7fcdca3a099b6b'
step_id: 'S317'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Gate docstring cross-references so a role naming a symbol its cited module does not export fails, with an anti-vacuity control proving the detector fires

## Scope

- `src/cadrumo/tests`

## Description

- Measure the dotted first-party cross-reference population and its violations
  before writing the gate, to establish whether a hard cut was affordable.
- Land the gate as a hard cut with no stored baseline, following the sibling
  well-formedness ratchet's idiom.
- Correct the six mis-citations the gate reds on.
- Prove recall on a missing symbol and a missing module, and precision on a
  facade symbol, a private symbol in its defining module, and a method
  resolved through its owning class.
- Floor the judged population as a bound so the assertion cannot go vacuous.

## Outcome

Gate landed and green; six real mis-citations fixed alongside it.

The measured population is 19,540 Sphinx object roles across the production
surface, of which 5,725 carry a dotted first-party target and are therefore
judgeable. Six were defects, which is what made the hard cut affordable: two
roles naming a MODULE with the callable role, the registry period-code scalar
alias cited twice on a package facade that does not export it, a database
filename cited on the config facade which re-exports only the FORMER name, and
a replay payload cited on the registry facade while it lives in the live
parity module.

The predicate is the finding worth carrying forward. Keyed on the export list
alone, the first draft reported sixty-two offenders, of which fifty-six were
CORRECT citations of a private symbol from the module that defines it. A
detector that spends its credibility on noise before it reports anything is
one nobody runs, so the shipped predicate is defines-or-exports and the
private-symbol case is pinned as its own precision control - the draft that
sank is the one the control now prevents returning.

The registry asymmetry is recorded because it is what made the bad citation
look right: the facade genuinely exports the period SELECTOR schema while not
exporting the period CODE alias beside it, so a reader writing the second by
analogy with the first produces a false reference that reads as obviously
fine.

## Notes

Stated reach, so the gate is not read as covering more than it does. Bare
anchors are excluded by design - they are the house style and carry no module
claim - so this reaches roughly a third of the roles in the tree. It judges
the citation and never the surrounding sentence: the two pre-split prose
claims corrected under S313 in the same commit both name a package that really
exists, so their roles resolve and only a reader catches them.

One unrelated red observed on the sibling docstring gate during verification,
recorded as peer churn rather than absorbed: the well-formedness ratchet's
ghost-parameter check fails on an aggregation binding helper documenting a
`deduction_authority` argument its signature does not accept. That file is
outside this row's surface and belongs to an active peer lane, so it is
reported and left.
