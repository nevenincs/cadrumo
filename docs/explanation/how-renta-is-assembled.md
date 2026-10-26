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

## One declaration, five source routes

Modelo 100 is the largest form the tool prepares - the 2025 version defines
over two thousand boxes (casillas) and two hundred formulas. Every value on it
arrives through a declared data source. The listing calls each of these contracts
a `binding`. The current Renta flow uses five broad routes. They are not the
complete list of source kinds for every modelo. List them for your
filing year:

```{cli-sequence} renta-assembly-bindings
:verify: Confirm the declaration lists its inputs and where their values come from.
```

- **Profile facts.** Who you are: tax id, residence comunidad, marital status, spouse and descendant data, disability grades, declaration type. These come from your taxpayer profile, one row per fact (the `renta-profile-*`, `renta-family-*`, and `renta-maritime-*` rows in the listing).
- **Totals from your records.** What your activity earned and spent: the year's classified income and deductible expense entries, added up per box and listed as the `renta-ledger-*` rows. These are the same records your quarterly filings read - Renta reads the whole year at once.
- **Prior filings folded in.** What you already reported during the year: the Modelo 130 or 131 instalments you paid, the retenciones reported on Modelos 111, 123, 190, and 193, and the activity income attributed on Modelo 184, where they exist (the rows the listing labels `relation_prefill`). The tool reads these from your own recorded filings, not from AEAT.
- **Last year's declaration.** What carries across years: a negative base liquidable from an earlier Renta carries forward from your own prior declaration recorded as filed, listed under the source `previous_filing`, so this year's declaration can offset it.
- **Stock inventory.** The closing-stock variation and stock purchases of an
  activity with stock. They come from your encrypted inventory register for the
  filing year, listed under the source `inventory`.

Everything else - employment income details, capital income, deductions your records cannot know about - is a box you fill in yourself when it applies to you. The full inventory for your year:

```{cli-sequence} renta-assembly-requires
:verify: Confirm the declaration's requirement inventory reads back.
```

For the 2025 version, the stock boxes 0177 (stock variation, increase), 0181
(purchase of inventory), and 0182 (stock variation, decrease) are filled from
the encrypted inventory register. Create and maintain it with
`aeat app ledger inventory`. The calculation refuses a value for these boxes
from `--casilla` or `--binding`. If the filing year has no inventory register,
the calculation warns and the three boxes stay at 0.

## How the quarterly filings fold in

Across the year you paid income tax in pieces: instalments on Modelo 130 (or
131 under módulos), and withholdings that clients or payers reported for
you. None of those was the final word - they were payments on account toward
one annual settlement, and Renta is where they meet. The declaration sets
them against your full-year income and settles the difference: what is
still owed, or what comes back.

The fold-in has a condition. Before the annual check passes, every earlier
filing the declaration depends on must be recorded as filed. A filing from
an earlier year also needs proof from AEAT. A same-year filing that is only
recorded as filed in Cadrumo passes with an advisory that it is not official. See what the declaration expects and what
currently blocks it:

```{cli-sequence} renta-assembly-dependencies
:verify: Confirm each dependency reports whether its required proof is present.
```

Each dependency row names the source modelo and period and whether the proof
of its filing is in place. A dependency that does not apply to you -
a retención modelo you never file, an instalment regime you are not under -
is left out based on your profile facts and shown as not applicable, never
silently skipped.

The tool never fabricates a missing prior period: a gap stays visible for
you to resolve. [How filings build on earlier ones](building-on-earlier-filings.md)
explains this design rule.

## What carries between years

A Renta with a negative base liquidable does not just end: the negative carries forward, and a later year's declaration offsets it. The carry reads your own prior declaration recorded as filed - and it re-confirms, at read time, that it was recorded under the version of the tax rules it claims. A prior declaration whose rules version no longer matches blocks the carry rather than silently importing figures computed under different law.

## Tracing any figure to its source and its law

After a calculation, every resolved value carries a typed record of where it
came from: the rule or formula that produced it, its operands, and its legal and source
references. The example starts from a calculated draft for an employee filer.
The read commands inspect that draft, and the last command looks up one box's
definition:

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
