# How your records become tax figures

This page explains where tax-form values come from. It follows a bank movement
through classification, calculation, and grounding without describing commands.

The linked how-to guides provide task steps.

The Agencia Estatal de Administración Tributaria (AEAT) owns modelos made of
numbered {term}`casillas <casilla>`.
Cadrumo prepares the figures locally; AEAT remains the authority that owns the
official form and receives the human-uploaded export.

## A bank movement means nothing on its own

A bank-statement line provides a date and amount without tax classification.
The same movement could represent customer income, a supplier payment, a
personal purchase, or an internal transfer.

Tax meaning isn't in the bank data. You add it. Until you do, a movement can't count toward any box on any form.

## Making a record tax-ready

To give a movement tax meaning, you turn it into a sorted, categorized record. A tax-ready record carries three things:

- a business, personal, or mixed decision;
- a category, such as customer sales or office supplies;
- and, for a mixed cost, the business-versus-personal split, so only the business share counts.

A record that has all of this is ready to feed into a calculation. To do this for your own movements, see [Classify transactions](../how-to/classify-transactions.md).

## Three ways to split a mixed cost

Some costs serve business and private uses. Examples include phone, internet,
and home-office electricity. Cadrumo supports three sources for the business
share.

The first is a percentage on a single record. You say this one phone bill is 60 percent business, and only that one record is split that way.

The second is a category default. Records in that category inherit the declared
business share unless a record overrides it.

The third is a ratio worked out from activity facts you declare to Cadrumo. For
example, an operator can record the size of a home office and the home so
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

The check changes nothing. It identifies records that need correction before
calculation. See [Import bank statements](../how-to/import-bank-statements.md)
for the readiness task.

## Which form, and which period

A calculation is always for one form, one year, and one period. The period decides which of your records count.

A period is a quarter, a single month, or a whole year. The tool turns it into a start and end date, then keeps only the records whose date falls inside that window. A first-quarter filing sees January through March; a March filing sees only March.

Choosing the right form for your activity is its own decision - see [Find out which modelos apply to you](../how-to/choose-modelo.md). For how quarters, months, and annual periods map to dates, see [Filing periods](../how-to/filing-periods.md).

## From records to numbered boxes

Calculation combines tax-ready period records with the active profile facts.

It then applies the rules the agency publishes for that form. The rules map
inputs to casillas and define their relationships. They can subtract deductible
costs from income before applying a tax rate.

Current profile facts and tax-ready records supply the inputs. Published rules
define the routing and arithmetic.

## Tracing a number back to the law

Grounded figures retain their mechanism and provenance. This includes the
binding or formula, declared legal and official-source references, and the
supplying record or observation. Manual inputs retain their source. Each
calculation also identifies its registry revision.

This is the point of the design. A reviewer can follow a casilla back through
its source records and declared grounding instead of treating the result as an
unexplained total. The [registry and legal-source
reference](../reference/registry-legal-api.md) defines those lookup fields.

## Where this sits in the journey

This page is part of Cadrumo's tax-preparation workflow - how your data flows from bank statement to filed form.

- Start at the overview: [Understanding Cadrumo's tax-preparation workflow](index.md).
- Continue to the next stage: [Editing and verifying a calculation](editing-and-verifying.md).
