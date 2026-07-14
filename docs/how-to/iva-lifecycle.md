# The IVA year: quarterly returns and the annual summary

This page covers one full IVA year for the same example taxpayer as
[the income-tax year](irpf-lifecycle.md): the opening credit balance,
four quarterly Modelo 303 returns with the IVA credit carrying between
them, an optional Modelo 349 branch for intra-community operations, and the
annual Modelo 390 summary that must reconcile with the four quarters.

Cadrumo (the `aeat` command) prepares local files for Spanish tax forms. It
does not submit them to the Agencia Estatal de Administración Tributaria
(AEAT). At each filing you upload the exported file yourself through the
AEAT portal.

The persona and the ledger continue from the income-tax run-through: Ana García
López, consultant, activity started January 1, 2026. The same sale and
expense rows you recorded there carry their IVA detail (taxable base, rate,
IVA amount), so they feed the IVA calculations without re-entry - one
ledger, two tax angles. If you have not run that run-through's stage 1 and
stage 2 `profile create` and `ledger add` commands, run them first.

The CLI prints help, labels, and messages in Spanish. This page keeps the
explanations in English.

## Prerequisites

A working `aeat` command, a master-key passphrase (the tool prompts for
it), and the profile and
first-quarter ledger rows from
[the income-tax year, stages 1 and 2](irpf-lifecycle.md). If you have no
profile yet, create one with `aeat config profile create <name>` — [Set up your
taxpayer profile](profile-setup.md) walks through it.

Confirm the IVA obligations:

```{cli-sequence} iva-lifecycle-applicability
:verify: Confirm why Modelo 303 applies this year.
@setup aeat config profile edit docs-sequence-sandbox --quiet --accept-defaults --activity-start-date 2026-01-01
@step Explain why and how often Modelo 303 applies this year.
@result aeat --format json app overview explain 303 --year 2026
@expect exit_code == 0
```

Ordinary non-exempt profiles file Modelo 303 quarterly; monthly
IVA-liquidation profiles such as REDEME file monthly. Ana is quarterly.

## Stage 1: the opening IVA credit balance

Modelo 303 keeps a running memory between periods: when a quarter leaves you
with more IVA paid than collected, the difference is a credit
(*compensación*) the next return can use. The tool tracks that credit in a
local wallet built from your Modelo 303 history - and the first time you use
the tool, that history is empty, so you declare the opening balance once.

Ana started her activity this year, so her true opening balance is zero:

```{cli-sequence} iva-lifecycle-wallet
:verify: Confirm the opening IVA credit balance is recorded and reads back.
@step Seed the opening balance as zero for a taxpayer starting this year.
aeat --format json app modelo iva-wallet seed --filing-year 2025 --period 4T --amount 0 --confirm
@step Show the wallet balance as of the filing year.
@result aeat --format json app modelo iva-wallet balance --as-of-year 2026
@expect exit_code == 0
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

The first quarter's rows are already recorded and classified with their IVA
detail (the sequence seeds them). Create, calculate, verify, file, and export
Modelo 303 for the quarter:

```{cli-sequence} iva-lifecycle-q1
:seed: iva-evidence-2026
:verify: Confirm the first quarter's IVA return verifies, files, and exports.
@step Open the first-quarter Modelo 303 draft.
aeat --format json app modelo work create --modelo 303 --year 2026 --period 1T
@step Calculate the quarter's IVA from the classified, evidenced ledger.
aeat --format json app modelo work calculate --modelo 303 --year 2026 --period 1T
@expect result.casilla_values.71 == "105.00"
@step Verify the draft; verification captures the evidence over the contributing rows.
aeat --format json app modelo work verify --modelo 303 --year 2026 --period 1T
@expect result.granted_verificado_completo == true
@step Record the local filed marker after you upload through AEAT yourself.
aeat --format json app modelo work file --modelo 303 --year 2026 --period 1T
@step Export the filed revision to a local fichero-BOE.
@result aeat --format json app modelo export --modelo 303 --year 2026 --period 1T --output ./modelo-303-2026-1T.boe
@expect exit_code == 0
@static aeat app modelo reconcile pull --modelo 303 --year 2026 --period 1T
```

Calculation routes the classified rows into the IVA boxes: the sale's 210 of
IVA charged (repercutido), the purchase's 105 of deductible IVA paid
(soportado), and the seeded wallet feeds the prior-compensation box. With
Ana's rows the quarter ends with IVA to pay - repercutido exceeds soportado.

Upload the file at the portal, then record the filing with `aeat app modelo
work file` and pull the justificante with `aeat app modelo reconcile pull` (both
shown in the sequence above) - the same closing rhythm as every filing in these
run-throughs.

The per-box detail of this workflow is
[Prepare a Modelo 303 IVA filing](modelo-303.md).

## Stage 3: a credit quarter, and the carry

Suppose the second quarter goes the other way: Ana buys a laptop and other
equipment, and her deductible IVA exceeds what she charged. Record the
quarter's rows (the income-tax run-through's stage 3 rows, plus the equipment -
an `aeat app ledger add` for the 1815-gross `equipo informatico` purchase with
315 of deductible IVA).

Run the same create-calculate-verify-export loop for `--period 2T`. When
deductible IVA exceeds charged IVA, the result box is negative and the
return declares the difference as credit to compensate - the quarter ends
with nothing to pay, and the wallet remembers the credit.

In the third quarter the carry shows itself: calculate `--period 3T` and the
prior-compensation box arrives from the wallet - the second quarter's credit
reduces what you pay now. Watch the balance move across the year with `aeat app
modelo iva-wallet balance --as-of-year 2026` (shown running in stage 1 above).

The balance reports the total, active, and expired credit and the lots it is
made of. Credit expires after the legal window, so the wallet also names the
next expiry year.

## Stage 4 (optional): intra-community operations and Modelo 349

Skip this stage unless you invoice clients or buy from suppliers in other EU
member states.

If Ana takes an EU client, the operations must also appear on the
recapitulative Modelo 349 - a listing, per EU operator, of the period's
intra-community operations. The operations are recorded as invoice records
carrying the counterparty's country and EU VAT number, and the VAT number is
worth checking against the VIES register first with `aeat app live verify
nif-iva DE123456789` (a live read from AEAT).

The full workflow - invoice records, the operation keys, rectifications of
earlier periods - is
[Prepare a Modelo 349 recapitulative declaration](modelo-349.md).
The same operations also feed the 303's intra-community boxes; keep the two
consistent by fixing the underlying records, never the declarations.

## Stage 5: the fourth quarter and the annual summary

Close the fourth quarter with the same loop in January (`--period 4T`).
Then prepare the annual Modelo 390 summary - annual token `0A`, same year - with
`aeat app modelo work create --modelo 390 --year 2026 --period 0A`, then `aeat
app modelo work calculate --modelo 390 --year 2026 --period 0A`.

Modelo 390 declares no new figures: it summarises the year, and its totals
must reconcile with the four quarterly returns you filed. The calculation
reads your filed Modelo 303 records; a missing or unevidenced quarter
blocks the annual verify with a cross-period finding that names it. The
verification includes the reconciliation rule - an annual total that
disagrees with the sum of the quarters is a blocking finding, not a warning.

Verify, export, file, and reconcile the annual summary with `aeat app modelo
work verify`, `aeat app modelo export`, `aeat app modelo work file`, and `aeat
app modelo reconcile pull`, each with `--modelo 390 --year 2026 --period 0A`.

The per-box detail is
[Prepare the annual Modelo 390 summary](modelo-390.md).

## What you completed

You carried the same taxpayer through a full IVA year: an opening wallet
balance declared once, a paying quarter, a credit quarter whose compensación
carried into the next return, an optional recapitulative branch, and an
annual summary that reconciled against the four quarters on your own record.

## Next steps

- [The income-tax year](irpf-lifecycle.md) - the same persona through IRPF.
- [Prepare a Modelo 303 IVA filing](modelo-303.md)
- [Prepare the annual Modelo 390 summary](modelo-390.md)
- [Prepare a Modelo 349 recapitulative declaration](modelo-349.md)
- [Deduct input IVA under prorrata](prorrata.md) - when your
  activity mixes IVA-taxed and exempt operations.
