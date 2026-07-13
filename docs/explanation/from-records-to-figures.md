# How your records become tax figures

This page explains where the numbers on your tax form come from. It walks through the idea, not the buttons. You'll see how a plain bank movement turns into a figure for each numbered box on an official form, and why the tool is built to let you explain every figure later.

This is background reading. When you're ready to actually do each step, follow the links to the how-to guides.

The forms are AEAT modelos made of numbered {term}`casillas <casilla>`.
Cadrumo prepares the figures locally; AEAT remains the authority that owns the
official form and receives the human-uploaded export.

## A bank movement means nothing on its own

A line on a bank statement is just a date and an amount. The money moved, but the statement doesn't know whether it was a customer paying you, a supplier you paid, your weekly groceries, or a transfer between your own accounts.

Tax meaning isn't in the bank data. You add it. Until you do, a movement can't count toward any box on any form.

## Making a record tax-ready

To give a movement tax meaning, you turn it into a sorted, categorized record. A tax-ready record carries three things:

- a business, personal, or mixed decision;
- a category, such as customer sales or office supplies;
- and, for a mixed cost, the business-versus-personal split, so only the business share counts.

A record that has all of this is ready to feed into a calculation. To do this for your own movements, see [Classify transactions](../how-to/classify-transactions.md).

## Three ways to split a mixed cost

Some costs serve both your business and your private life - a phone bill, home internet, the electricity in a home office. You can't deduct the whole amount, only the business share. The tool lets that split come from three places, depending on how precise you need to be.

The first is a percentage on a single record. You say this one phone bill is 60 percent business, and only that one record is split that way.

The second is a default for a whole category. You set a business share once for, say, all utility costs, and every record in that category inherits it unless you override it.

The third is a ratio worked out from activity facts you declare to Cadrumo. For
example, you can record the size of a home office and the size of the home so
Cadrumo derives the business share. These are operator-declared local facts,
not an official AEAT observation or confirmation, even when they describe facts
also used in an AEAT registration.

All three describe the same idea: keep only the part of a cost that genuinely belongs to the business.

## A readiness check before any sums

Before the tool adds anything up, it can check whether your records are sound. The readiness check looks at each record that falls inside the period you're filing and flags anything still missing:

- No business-versus-personal decision yet.
- No category on a deductible cost.
- No base amount, IVA (value-added tax) amount, or IVA rate where one is expected.
- A mixed cost with no split reference attached.
- An amount in a currency the tool can't yet convert to euros.

The check changes nothing. It just tells you which records aren't ready, so you fix the raw material before trusting any total. For how to run it, see the readiness section of [Import bank statements](../how-to/import-bank-statements.md).

## Which form, and which period

A calculation is always for one form, one year, and one period. The period decides which of your records count.

A period is a quarter, a single month, or a whole year. The tool turns it into a start and end date, then keeps only the records whose date falls inside that window. A first-quarter filing sees January through March; a March filing sees only March.

Choosing the right form for your activity is its own decision - see [Find out which modelos apply to you](../how-to/choose-modelo.md). For how quarters, months, and annual periods map to dates, see [Filing periods](../how-to/filing-periods.md).

## From records to numbered boxes

Here's where the figures appear. The tool reads two things: your tax-ready records for the period, and your profile - who you are and what you do.

It then applies the rules the agency publishes for that form. Those rules decide which input feeds which box, and how the boxes relate to each other. A cost you marked as office supplies lands in the box for that kind of expense. Income lands in its own box. From there, the rules add, subtract, and apply rates - total income minus deductible costs to reach a net figure, a rate applied to reach the tax due - until every box on the form holds a figure.

You don't wire any of this by hand. You make your records tax-ready and keep your profile current; the published rules do the routing and the arithmetic.

## Tracing a number back to the law

Grounded figures retain the mechanism and provenance available for that value:
the binding or formula that produced it, legal and official-source references
declared by the resolved registry rule, and the local record, observation, or
manual input that supplied it. A revision also identifies the registry revision
used for the calculation.

This is the point of the design. A reviewer can follow a casilla back through
its source records and declared grounding instead of treating the result as an
unexplained total. The [registry and legal-source
reference](../reference/registry-legal-api.md) defines those lookup fields.

## Where this sits in the journey

This page is part of Cadrumo's tax-preparation workflow - how your data flows from bank statement to filed form.

- Start at the overview: [Understanding Cadrumo's tax-preparation workflow](index.md).
- Continue to the next stage: [Editing and verifying a calculation](editing-and-verifying.md).
