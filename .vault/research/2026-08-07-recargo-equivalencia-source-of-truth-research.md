---
tags:
  - '#research'
  - '#recargo-equivalencia-source-of-truth'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:e1ffb10ce25f1d163107b330276ba7d99eb88de2175180cf9bae56a43c1baf64'
related: []
---

# `recargo-equivalencia-source-of-truth` research: `what establishes a recargo cuota today, and what the art. 161 table can and cannot express`

## Findings

### What establishes a recargo cuota in the shipped code today: the operator, not the table

Every recargo figure that reaches a Modelo 303 box originates on the transaction as
`recargo_amount`, an optional operator-supplied field. The IVA ledger aggregator scales
it by business proportionality and carries it onto the observation
(`src/cadrumo/application/aggregation/_iva_ledger.py:1269`), where the
`recargo_amount_sum` fact aggregates it into the bound casilla. No step derives the
figure from a rate. The supplier's invoice is, in effect, already the source of truth --
by omission rather than by decision.

### The art. 161 rate table exists, is grounded, and has no production consumer

`recargo_rate_for`, `load_recargo_rates` and `LIVA_ART_161_RECARGO` in
`src/cadrumo/domain/iva/_recargo_equivalencia.py` are referenced only by their own
definition, the `domain/iva` facade re-export, and that facade's `__all__`. A sweep of
production code (tests excluded) finds no call site. There is no dynamic reach either:
no `getattr` or `import_module` against the IVA facade resolves these names, and the
`liva-art-161:*` parameter ids are read only by the module that defines them.

The table is therefore decoration: grounded, complete-looking, and load-bearing for
nothing. That combination is the hazard, because a later reader reasonably infers from
its completeness that something depends on it.

### The table's key shape cannot express the transitional rates

`recargo_rate_for` takes a rate tier and no date. Between 2023-01-01 and 2024-09-30 the
reduced tier carries two recargo rates at once: the ordinary 1,4 % of LIVA art. 161 2.o,
and the 0,62 % that the transitional foodstuffs measures attach to their own 5 % IVA
rate. A tier cannot key both.

This is the same collision the Modelo 303 ordinario rate rungs carried until the
transitional-rate allocation landed: a tier stops determining a rate the moment a
transitional rate coexists with its tier's ordinary one. The resolution there was to key
on the applied rate. The same correction applies here, so any use of this table requires
re-keying on the applied rate and the operation date first.

### The transitional recargo rates are fully grounded in bundled corpus

Verified through the shipped `legal_reference_quotes_corpus` checker rather than by
counting text, because the resolved unit is normalised lowercase-unaccented. The reading
was bracketed by controls: a phrase that must be present in the foodstuffs measure
resolved present, and an unrelated-tax phrase resolved absent, so the checker
discriminates rather than answering uniformly.

`real-decreto-ley-20-2022:art-72`, in force 2023-01-01 to 2024-06-30, states a 5 % IVA
rate on oils and pasta with a recargo of 0,62 %, and a 0 % rate on the enumerated basic
foods with a recargo of 0 %. `real-decreto-ley-4-2024:art-1` continues that pair to
2024-09-30 and then states 7,5 % with a recargo of 1 % and 2 % with a recargo of 0,26 %.

Both catalogue entries are agent-prepared and carry an outstanding filing-grade operator
review. Neither should be read as human-reviewed grounding.

### Three provisions land on one Modelo 303 rung, which is why it reads as loose

The 2023 and 2024 record designs give one recargo rung a set of admissible Tipo values
rather than a single constant: zero, the ordinary super-reducido 0,5 %, and the
transitional 0,62 %. Those are three separate provisions -- the transitional measure's
zero-rate recargo, LIVA art. 161 3.o, and the transitional measure's reduced-rate
recargo -- sharing one printed rung. The design is not being imprecise; it is folding
three legal sources onto one line.

### A rate of zero is not the absence of a rate

`recargo_rate_for` returns nothing for both the zero and the exempt tier, and its
docstring reads that as the recargo regime not applying to either. The transitional
measure states a recargo of zero per cent for its zero-rated foods, which is a rate, not
inapplicability: such a supply sits inside the regime carrying the obligation at zero,
whereas an exempt supply sits outside it. The record designs corroborate this
independently by giving the zero tier its own recargo rung rather than omitting one.
Behaviour is identical today, which is why the conflation survives.

## Sources

Bundled corpus entries `real-decreto-ley-20-2022:art-72`, `real-decreto-ley-4-2024:art-1`
and `ley-37-1992:art-161`, read through the shipped corpus-quotation checker. Modelo 303
record designs for 2023, 2024 (both halves), 2025 and 2026, read from the bundled
diseno extracts. Shipped source at `src/cadrumo/domain/iva/_recargo_equivalencia.py` and
`src/cadrumo/application/aggregation/_iva_ledger.py`.
