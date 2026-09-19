---
tags:
  - '#audit'
  - '#registry-temporal-coverage'
date: '2026-08-27'
modified: '2026-08-27'
body_schema: 'body-v2'
body_hash: 'sha256:d0714947102a3d98df91c41b1a3c1abb2580c2450a38781ea7f12a65cc70db02'
related:
  - "[[2026-08-14-registry-temporal-coverage-plan]]"
  - "[[2026-08-14-registry-temporal-coverage-authority-grade-coverage-adr]]"
---

# `registry-temporal-coverage` audit: `coverage residue state`

## Scope

The campaign's coverage residue, measured at 2026-08-27 against the bundled
registry: every cell the temporal coverage matrix and the supported-year gap
projection cannot settle without a human ruling.

Recorded here rather than as source annotations, because the residue describes
the corpus rather than any module, and an annotation rots against the tree it
describes. The live figures regenerate with
`python -m dev.registry.analysis.coverage_residue_worklist`; this document
records the state and what each class of cell needs, not a copy of the rows.

## Findings

### coverage-residue | medium | the matrix resolves almost everything, and the remainder is one ambiguity plus one systematic shortfall

The matrix derives 1,720 declared cells and validates 1,718 of them. The whole
residue is 880 cells in two classes, and they need different rulings.

**Refused selection, 1 cell.** Modelo 308, filing year 2011, period `AD-HOC`
resolves to nothing because two revisions both claim it: `2009-2011-junio` and
`2011-julio-2015`. Only a reading of the governing orden settles which applies
across the July 2011 boundary. Both revisions declare applicability grade, so
no filing surface is affected today.

**Unbacked declaration, 879 cells** in three prerequisite kinds: 408 missing an
evidence-backed source cell, 342 missing a filing authority grade, 129 missing a
law-resolvable revision. Each is a decision about whether to ground the year,
lower the claim, or withdraw the cell -- not a derivation anyone can re-run.

### coverage-residue | high | the declared support window and the shipped revision set contradict each other

Measured separately and not previously recorded: **37 of the 58 bundled modelos
ship revisions covering years the registry does not declare supported.** The
declaration carries 2022 to 2026. The corpus reaches back to 2003 (Modelo 156),
2012 (Modelo 145) and 2013 (Modelo 165); Modelo 100 itself ships 2020 and 2021.

This is the reason `W02.P05.S25` cannot land. A supported-year refusal was
implemented at the authority snapshot boundary and withdrawn after producing 36
refusals across the registry suite and 8 more in the Modelo 100 suites -- every
one of them a correct test reading a revision the registry genuinely ships. No
placement of that refusal succeeds while the two year-sets disagree, so `S25`
depends on `W02.P05.S51`, which constrains the claimed-year set and is itself
blocked on acquiring historical AEAT design artefacts. The plan records no such
dependency.

## Recommendations

Record the `S25` to `S51` dependency on the plan, so the blocked set reads six
rows rather than five and nobody re-attempts the refusal before the claimed-year
contradiction is settled.

Adjudicate the Modelo 308 2011 `AD-HOC` boundary against the governing orden.
It is one cell and it is the only genuinely ambiguous selection in the corpus.

Treat the 879 unbacked cells as three separate rulings rather than one backlog.
The 129 missing a law-resolvable revision are the sharpest: the declaration
claims a year for which no revision resolves at all, which is a claim the corpus
cannot honour under any grade.

Regenerate the worklist rather than editing it. It is deterministic by
construction -- no clock, no run identity -- so a shrinking residue shows up as
a shrinking diff, and that property is gated by
`dev/registry/tests/test_coverage_residue_worklist.py`.
