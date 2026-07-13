# How filings build on earlier ones

Some forms depend on earlier periods. An annual summary may need quarterly
figures. An income-tax return may need instalments paid during the year. This
page explains carry-forward relationships and their evidence limits.

[How your records become tax figures](from-records-to-figures.md) explains a
single period. This page covers relationships between filings.

The Agencia Estatal de Administración Tributaria (AEAT) is the external tax
authority. The {doc}`glossary </_generated/glossary>` defines modelo, casilla,
justificante, value-added tax (IVA), personal income tax (IRPF), and RENTA.

## Why a later form needs earlier figures

Tax doesn't reset every quarter. The figures you report in one period often feed the next.

Two common shapes show up across the forms:

- **Annual summaries gather the year.** A yearly form rolls up the periods inside it. Modelo 390, for example, summarises the year's Modelo 303 IVA filings. Modelo 100 (RENTA) pulls together the income-tax instalments and withholdings you reported through the year.
- **Unused amounts carry into the next period.** If a Modelo 303 quarter leaves you with more IVA paid than collected, the difference becomes an unused amount carried into a later period - a IVA credit you keep until a later return can use it.

In both shapes, the later form depends on reported figures. Cadrumo carries
recorded values forward with their source revision and evidence.

## Earlier figures must be backed by evidence

A carried-forward figure depends on its source filing. Cadrumo therefore uses a
filing recorded as filed and retains its revision identity. An AEAT receipt can
provide additional evidence.

For carry-forward, Cadrumo uses only figures it has on record for the matching
modelo, year, and period. It does not invent a missing prior filing or silently
substitute zero. If a yearly form requires four filed quarters and only two are
available, the absent carry-forward evidence remains visible.

Carried values remain reviewable inputs, not authority decisions. Confirm that
each value matches the filing and evidence it cites.

## The running IVA credit balance

Cadrumo records unused IVA credit from Modelo 303. A later period can consume
that recorded balance as a carry-forward input.

That running record needs a true starting point. The first time you use the tool, it has no history of the credit you'd built up before. So you set the opening balance once - the unused IVA credit you were already carrying when you started. From there, each period updates the balance on its own.

An opening balance can be corrected until a recorded filing depends on it.
Cadrumo refuses a correction that would change the basis of that filing. The
refusal identifies the dependent filing.

To see the figures a calculation is using, read [Review and supply calculation inputs](../how-to/review-calculation-values.md). For the yearly IVA summary that draws on these periods, see [Prepare the annual Modelo 390 IVA summary](../how-to/modelo-390.md).

## The annual income-tax return pulls the year together

The annual income-tax return (RENTA) gathers instalments and withholdings from
the filing year. Those earlier amounts contribute to the annual settlement.

The annual return combines earlier instalments and withholdings with full-year
income. It then derives the remaining amount due or refundable.

RENTA uses the instalments and withholdings recorded from completed filings.
Review their cited revisions and evidence before relying on the result.

## What the tool checks, and what it leaves to you

Carry-forward has a narrow evidence boundary.

Cadrumo matches recorded earlier figures by modelo, year, and period. The
carry-forward mechanism excludes unconfirmed authority data, missing filings,
and unrelated observations.

Confirm that each carried value comes from the intended recorded filing. Compare
it with the AEAT receipt when available. Treat a missing period as an unresolved
dependency, not zero.

Cadrumo handles transfer and arithmetic. The operator confirms that each source
filing and its evidence match the intended carry-forward.

Separately invoked read-only AEAT retrieval can preserve the authority's filed
record or justificante as another evidence source. That evidence may confirm
the filing and revision used by later work. It cannot submit a return, alter
authority records, or request an AEAT recomputation.

Projection is a separate, explicitly invoked planning surface. A projection
may extrapolate from the quarters available and labels that result as an
estimate. Extrapolated values are not fabricated carry-forward evidence and do
not turn a missing filed period into a recorded filing.

## Where this sits in the journey

This page covers the connections between filings - why later forms depend on earlier ones and how figures carry forward. The [Understanding Cadrumo's tax-preparation workflow](index.md) overview maps where this fits among the other concepts. To go a level down into how a single period's figures are built from your records, read [How your records become tax figures](from-records-to-figures.md).

Once your figures are settled - including the ones carried in from earlier filings - the next concept is checking and sharing them. Continue with [Reviewing your numbers and producing the upload file](reviewing-and-exporting.md).
