---
tags:
  - '#exec'
  - '#minimo-descendientes-eligibility'
date: '2026-08-04'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:7d84a44608b1472ffddb43c0cde53392a2e900c34f0439b1c3721bf078c253ca'
step_id: 'S01'
related:
  - "[[2026-08-04-minimo-descendientes-eligibility-plan]]"
---

# Author the Art. 58.1 rentas-cap money parameter for revisions 2020-2025 with a legal-catalogue entry anchored to the bundled consolidated LIRPF clause

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/100/revisions/*/parameters/`
- `src/cadrumo/_data/registry/aeat/legal/`

## Description

## Outcome

The Art. 58.1 rentas cap ships as a registry money parameter for every revision 2020-2025,
valued 8.000 euros, with a legal-catalogue entry anchored to the bundled consolidated LIRPF
text. No Python literal carries the figure.

The anchor was verified verbatim by the coordinator, not only by the executor: the clause
"no tenga rentas anuales, excluidas las exentas, superiores a 8.000 euros, de:" is present
in the bundled corpus and the catalogue entry resolves against it.

The figure was cross-checked against two independent bundled authorities rather than the
corpus alone, per the rule that the bundled corpus is preferred but not infallible for
numeric amounts: the consolidated BOE text and every year's AEAT Manual Práctico across
2020-2025, which agree.

Law invariance across the served window is measured rather than assumed. The last amendment
to the article is Ley 26/2014, effective 1 January 2015, and every later note in the
consolidated file predates it, so one value is correct for all six revisions. The entry
carries that effective date with no end, satisfying the devengo-anchoring gate.

Non-tautology was proved by mutation, run in memory so no shippable-state window opened:
mutating the figure makes both the legal-corpus gate and the manual-citation gate refuse,
while the shipped value passes. A wrong figure could not have shipped silently.

One trap was caught and avoided. The first candidate anchor matched the manual, but inside
the cónyuge-con-discapacidad deduction rather than the descendiente cap, and Art. 61 norma
1a carries the same figure applied to the claimant instead. Both would have passed a naive
presence check. The final anchor discriminates, proved as a matrix against the sibling
article plus two fabricated-figure controls that match neither. This is the
required-text-proves-presence-never-attribution hazard, caught by the executor's own
discovery sweep.

## Notes
