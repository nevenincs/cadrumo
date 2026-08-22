# Deep dive: how the Renta declaration is assembled

This page covers how the annual Modelo 100 Renta declaration is assembled:
where each of its values comes from, how the year's quarterly filings fold
into it, what carries over from last year's declaration, and how to trace
any figure back to its source and its legal basis. It is the one deep-dive
page in this section - unlike its neighbours it names real commands, because
Renta is the filing where you most need to see for yourself how a value
arrived.

The commands are shown for the 2025 declaration (`--year 2025 --period 0A`);
substitute your filing year. They assume an active taxpayer profile, created
with `aeat config profile create` as
[Set up your taxpayer profile](../how-to/profile-setup.md) explains. The
step-by-step preparation lives in
[Prepare the annual Modelo 100 Renta declaration](../how-to/modelo-100.md).

## One declaration, four source routes used here

Modelo 100 is the largest form the tool prepares - the 2025 revision defines
over two thousand casillas and two hundred formulas. Every value on it
arrives through a declared data source. The binding listing calls each contract
a *binding*. The current Renta flow uses four broad routes. They are not the
complete source-kind taxonomy for every modelo. List them for your
filing year:

```{cli-sequence} renta-assembly-bindings
:verify: Confirm the declaration's bindings list with their four source kinds.
```

- **Profile facts.** Who you are: tax id, residence comunidad, marital
  status, spouse and descendant data, disability grades, declaration type.
  These come from your taxpayer profile, one binding per fact (the
  `renta-2025-profile-*` rows in the listing).
- **Ledger aggregations.** What your activity earned and spent: the year's
  classified income and deductible expense rows, aggregated per casilla and
  listed as the `renta-2025-ledger-*` rows. This is the same ledger your quarterly
  filings read - Renta reads the whole year at once.
- **Prior filings folded in.** What you already reported during the year:
  the Modelo 130 or 131 instalments you paid, and the retenciones reported
  on modelos 111, 123, 190, and 193 where they exist (the rows the
  listing labels `relation_prefill`). The tool reads these from your own
  filed records, not from AEAT.
- **Last year's declaration.** What carries across years: a negative base
  liquidable from an earlier Renta carries forward from your own filed
  prior declaration, listed under the source `previous_filing`, so
  this year's declaration can offset it.

Everything else - employment income details, capital income, deductions the
ledger cannot know about - is a manual casilla you supply when it applies to
you. The full inventory for your year:

```{cli-sequence} renta-assembly-requires
:verify: Confirm the declaration's requirement inventory reads back.
```

Stock inventory is one such current boundary. The encrypted inventory register
can record movements and calculate valuations, but it is not enrolled in the
Renta source mesh. For the 2025 revision, boxes 0177 (increase in stock
variation), 0181 (stock purchases), and 0182 (decrease in stock variation)
remain manual inputs. Box 0155 is not an inventory input and does not connect
the inventory register to the declaration.

## How the quarterly filings fold in

Across the year you paid income tax in pieces: instalments on Modelo 130 (or
131 under módulos), and withholdings that clients or payers reported for
you. None of those was the final word - they were payments on account toward
one annual settlement, and Renta is where they meet. The declaration sets
them against your full-year income and settles the difference: what is
still owed, or what comes back.

The fold-in is evidence-gated. Before the annual verify passes, every prior
filing the declaration depends on must be filed and evidenced on your
record. See what the declaration expects and what currently blocks it:

```{cli-sequence} renta-assembly-dependencies
:verify: Confirm each dependency reports whether its evidence is satisfied.
```

Each dependency row names the source modelo and period and whether its
clean-state evidence is satisfied. A dependency that does not apply to you -
a retención model you never file, an instalment regime you are not under -
is scoped out from your profile facts and shown as not applicable, never
silently skipped.

The tool never fabricates a missing prior period: a gap stays visible for
you to resolve. [How filings build on earlier ones](building-on-earlier-filings.md)
explains this design rule.

## What carries between years

A Renta with a negative base liquidable does not just end: the negative
carries forward, and a later year's declaration offsets it. The carry reads
your own filed prior declaration - and it re-confirms, at read time, that
the prior was filed under the registry
revision it claims. A prior whose revision no longer matches blocks the
carry rather than silently importing figures computed under different law.

## Tracing any figure to its source and its law

After a calculation, every resolved value carries typed provenance: the
binding or formula that produced it, its operands, and its legal and source
references. The setup steps calculate an employee filer's draft. The read
commands inspect that draft, and the final step looks up one box's definition:

```{cli-sequence} renta-assembly-provenance
:verify: Confirm every resolved value carries its legal and source references.
```

The JSON output of any of these commands carries `legal_refs` and
`source_refs` on every row. This is the property Cadrumo preserves end to
end: if an inspector asks why a box holds a figure, the answer is on your
machine - the records behind it, the rule that routed them, and the article
of law behind the rule.

## Where this sits in the journey

This page is part of the [how-it-works overview](index.md)
cluster and goes one level deeper than
[How filings build on earlier ones](building-on-earlier-filings.md), which
explains the cross-filing idea in general. The preparation workflow is
[Prepare the annual Modelo 100 Renta declaration](../how-to/modelo-100.md);
the quarterly instalments that feed it are covered in
[Prepare a Modelo 130 IRPF instalment](../how-to/modelo-130.md).
