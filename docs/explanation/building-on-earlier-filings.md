# How filings build on earlier ones

Some forms can't be filled from a single period's records alone. A yearly summary needs the quarters that came before it. An income-tax return needs the instalments you paid through the year. This page explains why that happens, how the tool carries figures forward from your earlier filings, and - just as important - what it leaves for you to check. It's for anyone preparing a form that depends on earlier periods or on the whole year.

If you want how a single period's figures are built from your records, see [How your records become tax figures](from-records-to-figures.md). This page is about the connections *between* filings.

A quick note on terms. A *modelo* is one of the agency's tax forms. AEAT is the Spanish tax agency (Agencia Estatal de Administración Tributaria). A *casilla* is a numbered box on a form. *IVA* is value-added tax; *IRPF* is personal income tax; *RENTA* is the annual income-tax return (Modelo 100). A *justificante* is the receipt the agency issues when you file.

## Why a later form needs earlier figures

Tax doesn't reset every quarter. The figures you report in one period often feed the next.

Two common shapes show up across the forms:

- **Annual summaries gather the year.** A yearly form rolls up the periods inside it. Modelo 390, for example, summarises the year's Modelo 303 IVA filings. Modelo 100 (RENTA) pulls together the income-tax instalments and withholdings you reported through the year.
- **Unused amounts carry into the next period.** If a Modelo 303 quarter leaves you with more IVA paid than collected, the difference becomes an unused amount carried into a later period - a IVA credit you keep until a later return can use it.

In both shapes, the later form can't stand on its own. It reaches back to figures you already reported. The tool carries those figures forward from your earlier filings so you don't re-enter them by hand.

## Earlier figures must be backed by evidence

A carried-forward figure is only as trustworthy as the filing it came from. So the carry-forward rests on a clear principle. A figure carried in from an earlier filing should come from a filing you actually completed and marked as filed. Where possible, it should come from one backed by the agency's receipt.

The tool carries forward the figures it *has on record* for the matching modelo, year, and period. It does not invent a prior period that isn't there. If you ask a yearly form to gather four quarters and only two are on record, the tool brings in the two it has - it doesn't fabricate the missing pair to fill the gap. That's deliberate. A guessed figure in a filing is worse than a visible blank you can act on.

Because of this, the figures it carries forward are a starting point you review, not a verdict you accept blindly. You confirm that each earlier figure came from a filing you completed and that it still reflects what you filed before you rely on it.

## The running IVA credit balance

The unused-IVA case has its own small piece of memory. When a Modelo 303 period leaves you with IVA credit, the tool keeps a running record of that unused IVA credit to carry forward and brings it into the next period's return.

That running record needs a true starting point. The first time you use the tool, it has no history of the credit you'd built up before. So you set the opening balance once - the unused IVA credit you were already carrying when you started. From there, each period updates the balance on its own.

People make mistakes with an opening balance, so there's a correction path. You can fix a wrong opening balance after the fact. One guard protects you: the tool refuses to change the basis of a period you've already completed and marked as filed. Rewriting a figure that a filed return already relied on would quietly change that return after the fact, so the correction is refused and names the filing that's in the way. If you hit that, the figure is locked because a filing already used it - which is exactly when you'd want it locked.

To see the figures a calculation is using, read [Review and supply calculation inputs](../how-to/review-calculation-values.md). For the yearly IVA summary that draws on these periods, see [Prepare the annual Modelo 390 IVA summary](../how-to/modelo-390.md).

## The annual income-tax return pulls the year together

RENTA - the annual income-tax return - is the clearest example of a form that lives on earlier figures. Across the year you report income tax in pieces: instalment returns as you go, and withholdings that others reported on your behalf. None of those is the final word. RENTA gathers them.

The yearly return draws on those instalments and withholdings from your earlier filings, sets them against your full-year income, and settles the final income-tax figure - what's still owed, or what comes back to you. The pieces you filed through the year aren't separate events; they're instalments toward one annual settlement, and the annual return is where they meet.

The same idea governs the figures: RENTA settles on the instalments and withholdings the tool has on record from filings you completed. You review those before trusting the result.

## What the tool checks, and what it leaves to you

It helps to be precise about the boundary here, because this is where a filing's accuracy is won or lost.

The tool finds and carries forward the earlier figures it has on record, matched by modelo, year, and period. That's the limit of what it does on its own. It does not silently treat unconfirmed or out-of-date agency data as final, it does not invent a prior period that isn't on record, and it does not quietly sweep up every figure it can find and assume each one is correct.

What it leaves to you is the judgement: that each carried-forward figure came from a filing you completed and marked as filed; that it matches the agency's receipt for that filing where one exists; and that a missing prior period is a real gap to resolve, not a zero the tool filled for you.

This division is the point. The tool removes the re-typing and the arithmetic; you keep the confirmation. A figure that flows from a quarter into a yearly summary, or from this period's credit into the next, is only as sound as your review of where it came from.

## Where this sits in the journey

This page covered the connections between filings - why later forms depend on earlier ones and how figures carry forward. The [Understanding the AEAT pipeline](index.md) overview maps where this fits among the other concepts. To go a level down into how a single period's figures are built from your records, read [How your records become tax figures](from-records-to-figures.md).

Once your figures are settled - including the ones carried in from earlier filings - the next concept is checking and sharing them. Continue with [Reviewing your numbers and producing the upload file](reviewing-and-exporting.md).
