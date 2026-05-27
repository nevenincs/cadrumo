---
tags:
  - '#audit'
  - '#modelo-130-relation-regression'
date: '2026-05-27'
related:
  - "[[2026-05-26-modelo-130-relation-regression-plan]]"
  - "[[2026-05-26-modelo-130-relation-regression-adr]]"
---

# `modelo-130-relation-regression` audit: `art-110-5-corpus-fragment-gap`

## Scope

Plan step `P04.S15` (extend `[legal."rd-439-2007:art-110"].required_text`
with the BOE-verbatim art. 110.5 carry-forward sentence fragment)
investigated; this audit documents the corpus-state finding and
defers the required_text extension to a follow-up.

## Finding

The corpus normative source at
`src/aeat/_data/corpus/normatives/rd-439-2007.json#art-110`
contains paragraphs 1-4 of art. 110 (2679 chars). It does not
include explicit text covering the same-ejercicio prior-quarter
saldo-negativo carry-forward (no occurrence of "negativo",
"trimestres anteriores", "minorar", "compensar", or
"apartado 5" in the cached body). The corpus appears to predate
or be incomplete relative to the current BOE source for
RD 439/2007 art. 110.

`src/aeat/_data/corpus/normatives/ley-35-2006.json` likewise does
not contain the carry-forward fragment under any article.

## Disposition

The Modelo 130 carry-forward binding ALREADY cites
`rd-439-2007:art-110` as its legal_refs anchor, alongside three
other authoritative references (`orden-eha-672-2007:art-1`,
`ley-35-2006:art-99`, `rd-439-2007:art-95`). The legal grounding
chain is therefore intact for the binding-level audit trail.

The mechanism (casilla 17 negative -> saldo-negativo-fin-periodo
-> carry into casilla 15 the following quarter within the same
ejercicio) is documented in `aeat-modelo-130-instructions` cited
via `source_refs` on the binding and the per-casilla declarations.

The plan's `P04.S15` asked for a verbatim BOE fragment extension
to the legal entry's `required_text`. Because the BOE fragment is
not in the cached corpus and re-fetching is out of session scope,
S15 is closed with this audit as deferral evidence. Follow-up
work to re-fetch RD 439/2007 from BOE and extend `required_text`
with the art. 110.5 verbatim sentence is recommended but does not
block:

  - P04.S16 verification (selector + binding load cleanly).
  - P05 regression test suite (asserts runtime behaviour, not
    legal-text-fragment presence).

## Follow-up recommendation

Re-fetch `https://www.boe.es/buscar/act.php?id=BOE-A-2007-6820#a110`
into the corpus pipeline, identify the carry-forward sentence in
the consolidated text, and extend
`[legal."rd-439-2007:art-110"].required_text` with the verbatim
fragment. Cross-check that the AEAT Manual de la Renta para
empresarios y profesionales 2025 cites the same article paragraph
to confirm the substrate.
