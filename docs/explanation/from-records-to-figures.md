# How your records become tax figures

This page explains where the numbers on your tax form come from. It walks through the idea, not the buttons. You'll see how a plain bank movement turns into a figure for each numbered box on an official form, and why the tool is built to let you explain every figure later.

This is background reading. When you're ready to actually do each step, follow the links to the how-to guides.

The forms in question are *modelos* (numbered official tax forms) that you send to the AEAT (the Spanish tax agency, the Agencia Estatal de Administración Tributaria). Each modelo is made of *casillas* (numbered boxes). Your job, with the tool's help, is to put the right figure in each box and to keep the evidence behind it.

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

The third is a ratio worked out from your official registration details. If you've recorded the facts behind your activity - for example, the size of a registered home office against the size of your home - the tool can work out the business share from those facts instead of asking you to guess a number.

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

Every figure the tool produces keeps three things attached: the rule that produced it, the law article behind that rule, and the section of the official manual that explains it. Input figures you entered yourself carry the same trail back to their source.

This is the point of the whole design. Spanish tax filing expects you to justify every number. If an inspector asks why a box holds a certain figure, you can show the records behind it and the rule and law that turned those records into that figure. Nothing is a black box.

## Where this sits in the journey

This page is part of understanding the AEAT pipeline - how your data flows from bank statement to filed form.

- Start at the overview: [Understanding the AEAT pipeline](index.md).
- Continue to the next stage: [Editing and verifying a calculation](editing-and-verifying.md).
