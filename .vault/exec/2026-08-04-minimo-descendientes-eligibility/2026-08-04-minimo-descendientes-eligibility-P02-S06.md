---
tags:
  - '#exec'
  - '#minimo-descendientes-eligibility'
date: '2026-08-04'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:fbc18fcc9bade2fef526f69b66423e7c66dc0c7eb662f162afa2cd94a5a4ef22'
step_id: 'S06'
related:
  - "[[2026-08-04-minimo-descendientes-eligibility-plan]]"
---

# Generalise the norma 1a prorrata from the shared-custody special case to the entitlement rule, keeping shared custody as one trigger and adding an explicit per-descendant override

## Scope

- `src/cadrumo/domain/contribuyente/family.py`

## Description

## Outcome

The norma 1a proration is generalised from the shared-custody special case to the
entitlement rule the law states. Shared custody remains one trigger among others rather than
the sole condition, and an explicit per-descendant override lets an operator state the answer
directly.

The gate condition holds: two entitled filers receive a prorated minimo where each previously
received the full amount. The anti-tautology pair is a conjunta return taking the full tranche
against an individual one halved, which no recomputation of the aggregate formula can satisfy
by itself.

One legal ruling the ADR did not state, decided by the executor and independently verified by
the coordinator against the bundled corpus: a conjunta return is NOT prorated. The
tributacion conjunta article applies the minimo once for the unidad familiar irrespective of
how many members it contains, and norma 1a prorates only where two or more contribuyentes are
each entitled, which means two separate returns each claiming. A joint return is one return.
Prorating it would halve a correct figure rather than correct an inflated one. The executor
offered to reverse this on one boolean if the coordinator disagreed. The coordinator does not
disagree, and the corpus reading is recorded here so the decision is auditable rather than
resting on assertion.

CORRECTION, and it overturns part of what this record accepted.

The conjunta ruling above is right for a MARRIED couple and wrong as a general rule. An
AEAT worked example caught it: two printed conjunta scenarios disagree, one taking full
tranches and one keeping them prorated. The difference is marriage, not declaration type.

Art. 82.1 declares two modalities of unidad familiar, and the coordinator verified both
verbatim in the bundled corpus. The first is the one Art. 84 addresses and the one the
original ruling reasoned from: the non-legally-separated spouses and their children. The
second, which applies in the absence of a marriage, is "la formada por el padre o la madre y
todos los hijos" -- ONE parent, not both. So an unmarried couple cannot form a single unit.
The other progenitor remains a separate contribuyente entitled to the same descendant, and
norma 1a still prorates.

The original reasoning was sound within its scope and the coordinator's independent
verification confirmed it there. What neither caught was that the scope was narrower than
the rule being written: a conjunta return by an unmarried couple was collapsed into the
married case and over-granted by 2.550 euros, which is an under-declaration -- the same
class of defect this campaign exists to close, reintroduced by the fix for it.

The derivation now turns on marriage rather than on the declaration type alone.

This is the argument for grounding against printed figures rather than against reasoning,
made concretely. The ruling was adjudicated by a design authority, independently verified by
the coordinator against the corpus, and still wrong at an edge neither had reason to probe.
The oracle found it in one measurement because the manual prints both cases side by side.

## Notes
