(the-iva-year-quarterly-returns-and-the-annual-summary)=
# The VAT year: quarterly returns and the annual summary

This page covers one full VAT year for the same example taxpayer as
[the income-tax year](irpf-lifecycle.md): the opening credit balance,
four quarterly Modelo 303 returns with the VAT credit carrying between
them, an optional Modelo 349 branch for intra-community operations, and the
annual Modelo 390 summary that must reconcile with the four quarters.

Cadrumo (the `aeat` command) prepares local files for Spanish tax forms. It
does not submit them to the Agencia Estatal de Administración Tributaria
(AEAT). Modelo 303 export writes a file whose envelope carries Cadrumo's
all-zero development software identity, which AEAT does not accept, so you
enter the calculated box values through the portal.

The persona and the records continue from the income-tax run-through: Ana García
López, consultant, activity started January 1, 2026. The same sale and expense
entries you recorded there carry their VAT detail (taxable base, rate, VAT
amount), so they feed the VAT calculations without re-entry - one set of records,
two tax angles. If you have not run that run-through's stage 1 and stage 2
`profile create` and `ledger add` commands, run them first.

The examples in this documentation are recorded in English. `aeat` prints its
messages in Spanish unless you
[choose another language](profile-setup.md#choose-the-output-language).

## Prerequisites

A working `aeat` command, your passphrase (the tool prompts for it), and
the profile and first-quarter entries from [the income-tax year, stages 1 and
2](irpf-lifecycle.md). If you have no profile yet, create one with `aeat config
profile create <name>`. [Set up your taxpayer profile](profile-setup.md) walks
through it.

Confirm the VAT obligations:

```{cli-sequence} iva-lifecycle-applicability
:verify: Confirm why Modelo 303 applies this year.
```

Ordinary non-exempt profiles file Modelo 303 quarterly; monthly
VAT-liquidation profiles such as REDEME file monthly. Ana is quarterly.

(stage-1-the-opening-iva-credit-balance)=
## Stage 1: the opening VAT credit balance

Modelo 303 keeps a running memory between periods: when a quarter leaves you
with more VAT paid than collected, the difference is a credit
(*compensación*) the next return can use. The tool tracks that credit in a
local wallet built from your Modelo 303 history - and the first time you use
the tool, that history is empty, so you declare the opening balance once.

Ana started her activity this year, so her true opening balance is zero:

```{cli-sequence} iva-lifecycle-wallet
:verify: Confirm the opening VAT credit balance is recorded and reads back.
```

If you migrate to the tool mid-history, seed the credit you were actually
carrying instead of zero. Check the wallet at any time with `aeat app modelo
iva-wallet balance --as-of-year 2026`.

Mistakes have a correction path (`aeat app modelo iva-wallet correct`,
with `--reason` and `--confirm`) - but one guard is absolute: a seeded
balance that an already-filed Modelo 303 has consumed is refused, because
correcting it would silently change a filed return. The refusal names the
filing in the way. If you hit it, the figure is locked exactly when you
would want it locked.

## Stage 2: the first quarterly return

The example starts from the first quarter's entries, already recorded and classified with their VAT detail. Create, calculate, check and record the filing of Modelo 303 for the quarter; the export step writes the file with the all-zero development software identity:

```{cli-sequence} iva-lifecycle-q1
:verify: Confirm the first quarter's VAT return passes the check, records the filing, and exports with the development identity.
```

Calculation routes the classified entries into the VAT boxes: the sale's 210 of
VAT charged (repercutido), the purchase's 105 of deductible VAT paid (soportado),
and the seeded wallet feeds the prior-compensation box. With Ana's rows the
quarter ends with VAT to pay - repercutido exceeds soportado.

Enter the calculated box values at the portal, then record the filing with `aeat app modelo work file` and download the AEAT receipt with `aeat app modelo reconcile pull`. The first-quarter sequence runs the first command and shows the second as an example that is not run. This is the same closing rhythm as every filing in these run-throughs.

The per-box detail of this workflow is
[Prepare a Modelo 303 VAT filing](modelo-303.md).

## Stage 3: a credit quarter, and the carry

Suppose the second quarter goes the other way: Ana buys a laptop and other
equipment, and her deductible VAT exceeds what she charged. When deductible VAT
exceeds charged VAT, the result box is negative and the return declares the
difference as credit to compensate: the quarter ends with nothing to pay, and
the wallet remembers the credit.

Record the equipment purchase, then run the same chain as the first quarter:

```{cli-sequence} iva-lifecycle-q2
:verify: Confirm the equipment purchase records and the second-quarter draft opens.
```

The commands from `work calculate` onwards each read the first quarter, recorded as filed, that the credit carries from, so they are shown as examples that are not run. Link the equipment supplier's invoice to the entry before you calculate: a quarter that claims deductible VAT cannot be filed until every deductible entry carries its invoice. [Attach invoices and receipts to transactions](ledger-evidence.md) walks through it.

In the third quarter the carry shows itself: the same chain with `3T` brings the
prior-compensation box from the wallet, so the second quarter's credit reduces
what you pay now. Watch the balance move across the year with the wallet balance
command shown running in stage 1.

The balance reports the total, active, and expired credit and the lots it is
made of. Credit expires after the legal window, so the wallet also names the
next expiry year.

## Stage 4 (optional): intra-community operations and Modelo 349

Skip this stage unless you invoice clients or buy from suppliers in other EU
member states.

If Ana takes an EU client, the operations must also appear on the recapitulative
Modelo 349 - a listing, per EU counterparty (operador intracomunitario), of the
period's intra-community operations. The operations are recorded as invoices
carrying the counterparty's country and EU VAT number, and the VAT number is worth
checking against the VIES register first. That check is a live read from AEAT, so
it is shown as an example that is not run:

```{cli-sequence} iva-lifecycle-vies
```

The full workflow - invoices, the operation keys, rectifications of earlier
periods - is [Prepare a Modelo 349 recapitulative declaration](modelo-349.md). The
same operations also feed the 303's intra-community boxes; keep the two consistent
by fixing the underlying records, never the declarations.

## Stage 5: the fourth quarter and the annual summary

Close the fourth quarter with the same `4T` chain in January. Then prepare the annual Modelo 390 summary, annual period code `0A`, same year. Modelo 390 adds no new amount to pay: it summarises the year, and its totals must reconcile with the four quarterly returns you filed. The calculation reads your Modelo 303 declarations recorded as filed; a quarter that is missing or has no proof of filing blocks the annual check with an issue across periods that names it. The check includes the reconciliation rule: an annual total that disagrees with the sum of the quarters is an issue that blocks filing, not a warning.

Open the annual summary, then run the same chain as a quarter:

```{cli-sequence} iva-lifecycle-annual
:verify: Confirm the annual Modelo 390 summary uses the latest published form for 2025.
```

The commands from `work calculate` onwards each use all four quarters recorded as filed, so they are shown as examples that are not run until every quarter of the year is recorded as filed.

The per-box detail is
[Prepare the annual Modelo 390 VAT summary](modelo-390.md).

## What you completed

You carried the same taxpayer through a full VAT year: an opening wallet
balance declared once, a paying quarter, a credit quarter whose compensación
carried into the next return, an optional recapitulative branch, and an
annual summary that reconciled against the four quarters on your own record.

## Next steps

- [The income-tax year](irpf-lifecycle.md) - the same persona through IRPF.
- [Prepare a Modelo 303 VAT filing](modelo-303.md)
- [Prepare the annual Modelo 390 VAT summary](modelo-390.md)
- [Prepare a Modelo 349 recapitulative declaration](modelo-349.md)
- [Deduct input VAT under prorrata](prorrata.md) - when your
  activity mixes VAT-taxed and exempt operations.
