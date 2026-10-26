---
tags:
  - '#reference'
  - '#advisory-grounding'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:206a5679b4ab1e0c650ee83d688d914e68886ee094f1bf10e635b40f29c73669'
related: []
---

# `advisory-grounding` reference: `Advisory provision-citation sites and their reachable refs`

Grounding for the decision on how a calculation advisory carries the provision it
asserts. Two measurements compose here: an earlier census of
`CalculationSourceDiagnostic` construction sites, and the per-site read that
answers the question that census deliberately stopped at.

## Summary

The earlier census, across the application package: 83 construction sites in 26
modules, exactly one passing typed `legal_refs` or `source_refs`. Two caveats
travel with that figure, both confirmed here rather than inherited. It counts
SITES rather than distinct advisories, so the denominator is coarser than it
looks. And its prose classification is a regex over single-line string literals
that cannot tell a docstring from an operator-facing message, so its module count
is an upper bound.

The per-site read covers the ten modules that census named. It parses each
construction's own keyword list with `ast` rather than reading the file, because
an earlier probe asking whether a FILE mentions `legal_refs` reported five
grounded modules and collapsed to one when the arguments were parsed. The loose
instrument failed in the flattering direction.

    sites parsed across the ten modules                      34
    passing typed refs                                        1
    asserting a provision in an operator-facing message      21
    asserting one with no registry object anywhere in reach   5

## The feared population is empty

The question that prompted this work was whether an advisory asserts a provision
the registry cannot corroborate. It does not. Every provision cited in prose has
a legal-catalogue entry. Eleven families probed, eleven present: `ley-37-1992`
arts. 25, 75, 95, 97, 103, 104, 105 and 106; `ley-35-2006:art-101`; `rd-439-2007`
with twenty entries; `rd-1065-2007` with eleven.

Recorded because a later reader noticing untyped article literals will otherwise
re-run this panic from the start.

## Three populations, and the largest is a precision gap

**A. The casilla already carries the exact provision.** Small. Casilla `0513`
carries `ley-35-2006:art-56`, `art-58` and `art-61`, and one advisory asserts
plain "Art. 58".

**B. The catalogue carries the exact provision, the casilla does not reference
it.** The largest, and the population nobody predicted.

| the advisory asserts | catalogue entry | on the casilla it addresses |
| --- | --- | --- |
| Art. 58.1 | `ley-35-2006:art-58-1` | no, casilla carries `art-58` |
| Art. 61 norma 2 | `ley-35-2006:art-61-norma-2` | no, casilla carries `art-61` |
| Art. 81.2 | `ley-35-2006:art-81-2` | no, casilla `0613` carries only `art-81` |
| Art. 81.3 | `ley-35-2006:art-81-3` | no, same |
| LIVA arts. 104-105 | `ley-37-1992:art-104`, `art-105` | partly, casilla has 104 not 105 |
| LIVA 103.Dos.2, art. 106 | `ley-37-1992:art-103`, `art-106` | no, that site holds no casilla |

**C. No registry object in scope at all.** Five modules hold no revision,
snapshot or casilla definition anywhere: the invoice-devengo advisory, the
retencion-rate advisory, the invoice source resolver and the prior-payment
advisory. Every provision they cite has a catalogue entry, so this is threading,
not grounding.

**D. One false positive.** The evidence advisory's `LIVA art. 97` literals sit in
its module docstring and two comments; its single construction asserts nothing.

## The finding that decides the remedy

The one correct instance unions `casilla.legal_refs` with `binding.legal_refs`
and mints nothing. That is right for an advisory about the casilla's own
computation, and wrong for an advisory about an ELIGIBILITY RULE governing the
casilla's input, which is what most of these are. "Art. 61 norma 1 halves this"
is a claim about the rule that produced the number, not about the box holding it.

So reading refs off the casilla produces a COARSER or PARTIAL ref than the claim.
An advisory stating that art. 81.3 prorates the increment per child would emerge
carrying whole-article `art-81`: typed, green, and less precise than the sentence
beside it. **The prose is currently more precise than the typed path would be.**

## The art-81 ordering hazard

Casilla `0613` carries exactly one ref, `ley-35-2006:art-81`. That catalogue
entry's `corpus_ref` points at the per-article excerpt audited on 2026-08-10 and
found to be a two-vintage hybrid: it lacks the 81.2 turning-three extension, the
81.3 complemento-de-ayuda-para-la-infancia exclusion and the 150-euro increment.
Those are the clauses these advisories assert.

## What this reference does not establish

- Site counts cover the ten named modules, not all 26 the original census spans.
  The twelve modules asserting nothing were not re-read.
- That a population-B entry is the RIGHT ref is a tax-review judgement per site.
  This establishes that an entry exists at the claimed granularity, never that it
  is the provision that governs.
- The 83 and the 34 have different scopes and neither counts distinct advisories.
