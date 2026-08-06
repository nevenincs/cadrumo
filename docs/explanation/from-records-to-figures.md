# How your records become tax figures

This page covers where the numbers on your tax form come from: how a plain
bank movement turns into a figure for each numbered box on an official form,
and why the tool is built to let you explain every figure later. It walks
through the idea, not the buttons - the how-to guides linked from each
section carry the commands.

The forms in question are modelos that you send to the {term}`AEAT`. Each modelo is made of {term}`casillas <casilla>`. Your job, with the tool's help, is to put the right figure in each box and to keep the evidence behind it.

## A bank movement means nothing on its own

A line on a bank statement is just a date and an amount. The money moved, but the statement doesn't know whether it was a customer paying you, a supplier you paid, your weekly groceries, or a transfer between your own accounts.

Tax meaning isn't in the bank data. You add it. Until you do, a movement can't count toward any box on any form.

## Making a record tax-ready

To give a movement tax meaning, you turn it into a sorted, categorized record. A tax-ready record carries three things:

- a business, personal, or mixed decision;
- a category, such as customer sales or office supplies;
- and, for a mixed cost, the business-versus-personal split, so only the business share counts.

A record that has all of this is ready to feed into a calculation. To do this for your own movements, see [Classify transactions](../how-to/classify-transactions.md).

## Splitting a mixed cost, and checking readiness

Some costs serve both your business and your private life - a phone bill,
home internet, a home office. Only the business share counts, and the split
can come from a percentage on the single record, a saved default for the
whole category, or a ratio worked out from your registered facts - see
[the mixed-use workflow](../how-to/classify-transactions.md#classify-mixed-use-transactions).

Before the tool adds anything up, a readiness check flags each record in the
period that is still missing a decision, a category, a tax figure, a split
reference, or a convertible currency. The check changes nothing; it tells
you which records are not ready so you fix the raw material before trusting
any total - see the readiness section of
[Import and manage transactions](../how-to/import-bank-statements.md).

## Which form, and which period

A calculation is always for one form, one year, and one period. The period decides which of your records count.

A period is a quarter, a single month, or a whole year. The tool turns it into a start and end date, then keeps only the records whose date falls inside that window. A first-quarter filing sees January through March; a March filing sees only March.

Choosing the right form for your activity is its own decision - see [Find out which modelos apply to you](../how-to/choose-modelo.md). For how quarters, months, and annual periods map to dates, see [Period tokens and dates](../how-to/filing-calendar.md#period-tokens-and-dates).

## From records to numbered boxes

Here's where the figures appear. The tool reads two things: your tax-ready records for the period, and your profile - who you are and what you do.

It then applies the rules the agency publishes for that form. Those rules decide which input feeds which box, and how the boxes relate to each other. A cost you marked as office supplies lands in the box for that kind of expense. Income lands in its own box. From there, the rules add, subtract, and apply rates - total income minus deductible costs to reach a net figure, a rate applied to reach the tax due - until every box on the form holds a figure.

You don't wire any of this by hand. You make your records tax-ready and keep your profile current; the published rules do the routing and the arithmetic.

## Tracing a number back to the law

Every figure the tool produces keeps three things attached: the rule that produced it, the law article behind that rule, and the section of the official manual that explains it. Input figures you entered yourself carry the same trail back to their source.

This is the point of the whole design. Spanish tax filing expects you to justify every number. If an inspector asks why a box holds a certain figure, you can show the records behind it and the rule and law that turned those records into that figure. Nothing is a black box.

## Where this sits in the journey

This page is part of understanding the AEAT pipeline - how your data flows from bank statement to filed form.

- Start at the [how-it-works overview](index.md).
- Continue to the next stage: [Editing and verifying a calculation](editing-and-verifying.md).
