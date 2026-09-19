---
tags:
  - '#adr'
  - '#period-revision-resolution'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:96cd58218a39b7a05e2dd00ad8ca5bb7b8436c73cd8b2ebfff3eae8d1a6c1942'
related:
  - "[[2026-06-10-period-revision-resolution-adr]]"
  - '[[2026-06-10-period-revision-resolution-research]]'
---
# `period-revision-resolution` ADR: an AD-HOC work target must carry its operation date | (**status:** `proposed`)

## Context

This blocks the modelo 308 filing-year-2011 resolution gap. No registry datum
changes under this decision.

`aeat-registry-authority-flow` requires every production calculation, verification,
filing, export and projection path to resolve its revision from
`(modelo, filing_year, period)`. A non-overlap window gate is supposed to guarantee
that triple selects exactly one revision.

Modelo 308 filing year 2011 selects TWO:

    on=None        -> AmbiguousRevisionSelectionError: 2009-2011-junio, 2011-julio-2015
    on=2011-03-15  -> 2009-2011-junio
    on=2011-09-15  -> 2011-julio-2015

The registry data is not at fault. AEAT publishes the split itself, naming the two
record designs *"Ejercicios 2009 a 2011-julio"* and *"Ejercicios 2011-julio a 2015"*,
and the registry models it at day granularity: `valid_to = 2011-06-30` against
`valid_from = 2011-07-01`.

The boundary is fixed by CALENDAR DATE, not by ejercicio. Orden EHA/1033/2011,
which substitutes anexo II of Orden EHA/3786/2008, says only:

> La presente Orden entrará en vigor el día 1 de julio de 2011.

That is materially different from the `"aplicable, por primera vez, a las
declaraciones correspondientes al ejercicio YYYY"` formula that governs the annual
informativas. There is no ejercicio in this clause to key a revision on.

Checked against the bundled corpus rather than recollection. The clause is verbatim
in `corpus/normatives/html/orden-eha-1033-2011.html`, under `Disposición final única.
Entrada en vigor`, and the stronger fact is a negative: across the whole
1,971-word orden the word *ejercicio* occurs **zero** times, while *anexo II*
occurs four times and *308* twelve. The governing instrument carries no
ejercicio-keyed applicability formula anywhere, so there is nothing in it a
revision could be keyed on except the date.

The same orden supplies affirmative support for the axis this ADR adds. Its
refund provision runs the deadline from the operation itself -- "en el plazo de
tres meses desde que se haya realizado la entrega de bienes que origina el
derecho a la devolución" -- so the law already keys this modelo's obligations to
the event date. An AD-HOC work target carrying its operation date restates a
fact the governing orden relies on; it does not invent an axis.

On the call-site count: 30 production call sites reach `select_revision`, and the
4 passing `on=` are all registry-internal pass-throughs (`authority.py`,
`_snapshot_internals.py`). Every application-layer site -- prefill, calculate
input, work review, projection, data inventory -- resolves without a date, so no
application path could supply one today even if the registry asked.

Modelo 308 is filed AD-HOC — one declaration per settlement event, as the operation
occurs — and `AD-HOC` is its only period token. A period token carries no month, so
the period axis cannot partition a mid-year boundary the way modelo 303's 2024 split
does with `2024-hasta-08-y-2t` / `2024-desde-09-y-3t`.

So the triple is structurally insufficient for this modelo class: the fact that
selects the revision — WHEN the operation happened — is not in it. Measured on the
tree, only 4 production call sites pass `on=`, so in practice this resolves to a
refusal.

## Decision

**An AD-HOC work target carries its operation date, and AD-HOC revision resolution
requires it.**

1. A work target whose period token is `AD-HOC` declares the settlement/operation
   date as a required axis. It is the date of the event the declaration reports,
   not a filing timestamp, and it is therefore clock-free and stable.
2. `select_revision` on an AD-HOC target resolves with that date supplied. Refusing
   when it is absent stays correct and stays loud.
3. The `(modelo, filing_year, period)` mandate is unchanged for every periodic and
   annual modelo. This adds a third axis only where the period token cannot carry
   a month, and the axis is still law-determined: the date selects, the operator
   never names a revision.

## Rejected alternatives

**Invent period tokens** (`AD-HOC-H1` / `AD-HOC-H2`, or a month-qualified token).
This fabricates AEAT period grammar. `aeat-registry-authority-flow` forbids an
alternate boundary grammar outright, and the tokens would exist only to satisfy a
resolver — nothing in AEAT's publication uses them.

**Narrow the period_selector year ranges so they do not overlap.** Either
direction is wrong on the law: capping the first era at 2010 makes January-June
2011 resolve under the July design, and starting the second at 2012 makes
July-December 2011 resolve under the superseded one. Both silently compute a real
declaration under norms that did not govern it — the exact defect class the
revision-resolution mandate exists to prevent.

**Soften the overlap gate to tolerate date-disjoint windows.** The gate would then
report clean for a year the application genuinely cannot serve on the mandated
triple. The overlap is a true finding; hiding it does not make resolution work.

**Leave it.** The current behaviour fails CLOSED — it raises rather than guessing,
so no wrong figure is ever produced — and the affected window is a single historical
year whose filing period closed in 2012. That is why this is not urgent. It is still
a real hole: modelo 308 cannot be computed for 2011 through the sanctioned path, and
the same shape returns for any future modelo AEAT splits mid-year on a date.

## Consequences

- The AD-HOC work-target model gains a required operation-date field, and its
  persistence and CLI surfaces gain it with them.
- Resolution for AD-HOC targets passes that date; the ambiguity disappears without
  any change to registry data, which was already correct.
- The overlap gate can then assert uniqueness for AD-HOC modelos on the same terms
  as everything else, rather than being weakened.
- Until this is implemented, `test_every_modelo_resolves_exactly_one_revision_for_every_filing_year_through_today`
  stays red on modelo 308 / 2011, and that is the honest state.
