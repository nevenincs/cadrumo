# The income-tax year: four instalments and the annual Renta

This page covers one full IRPF year for an example taxpayer: four quarterly
Modelo 130 instalments, each building on the ones before it, closing with
the annual Modelo 100 Renta declaration that gathers the whole year. You
start from an empty store; by the end you have prepared and filed every
IRPF filing the year asks of a self-employed consultant.

Cadrumo (the `aeat` command) prepares local files for Spanish tax forms. It does
not submit them to the Agencia Estatal de Administración Tributaria (AEAT). For
Modelo 130 it writes a local fichero-BOE file that you present through the AEAT
portal.

Meet the persona this run-through follows: Ana García López, a consultant
(*consultoría*) who started her activity on January 1, 2026, invoices her clients
with 21 percent VAT, and buys office material as she goes. The same persona and
the same records continue in [The VAT year](iva-lifecycle.md) - the two
run-throughs describe the same business from two tax angles.

The examples in this documentation are recorded in English. `aeat` prints its
messages in Spanish unless you
[choose another language](profile-setup.md#choose-the-output-language).

## Prerequisites

You need a working `aeat` command (see
[Install Cadrumo](../workstation-setup.md)) and a master-key
passphrase. `aeat` encrypts your data with a passphrase and prompts for it
the first time each command runs.

## Stage 1: set up the taxpayer

Create the profile with `aeat config profile`, as [Set up your taxpayer
profile](profile-setup.md) walks through. The documentation sandbox provisions its
own profile, so this create is shown as an example that is not run:

```{cli-sequence} irpf-lifecycle-profile
```

The `--name` and `--surnames` are required: filing refuses without the
taxpayer's name. The `--activity-start-date` marks when the activity began,
so `aeat` does not look for a filing from before your first period. The
sample `--tax-id` has the shape of a Spanish citizen's NIF; use your own
NIF or NIE for a real profile. `--irpf-income-categories actividad_economica`
declares that your income comes from an economic activity, which is what makes
Modelo 130 apply.

Confirm what the year will ask of Ana:

```{cli-sequence} irpf-lifecycle-agenda
:verify: Confirm the year's filing calendar and Modelo 130 applicability read back.
```

The calendar covers 2026, so it lists the Modelo 130 windows for the first
three quarters (April, July, and October) next to the Modelo 303 windows.
The January window for the fourth quarter and the annual Renta window open
in the following year, outside that range. `explain` shows why Modelo 130
applies: an activity under estimación directa.

## Stage 2: the first quarter

Record the first quarter's activity - one sale, one expense. The `--amount` is the
gross total (taxable base plus VAT), and an expense entry needs a `--category-id`
(list the valid ids with `aeat app ledger categories`).

Register the supplier's invoice for that expense first. It takes its VAT rate
as a percentage (`--iva-rate 21`), while `ledger add` takes a decimal (`0.21`).
Then link it to the expense entry with `--purchase-invoice-evidence-id` before
you calculate. An
expense entry that claims deductible VAT cannot be filed without its invoice. A
draft bundles its supporting documents at the moment you check it, so an invoice
linked after that never reaches the filing.

Create and calculate the first instalment. Modelo 130 is cumulative, and a
true first period has no history, so the three prior-period carries are
passed as zeros - this is the only quarter where you do this. The sequence
below registers the invoice, records the quarter's two entries, creates and
calculates the draft, checks it, and exports it. The commands that record the
filing and reconcile, which close the quarter, follow as examples that are not run:

```{cli-sequence} irpf-lifecycle-q1
:verify: Confirm the first instalment passes the check and exports locally.
```

The figures show the year so far: 1000 earned, 500 spent, and an instalment
of 20 percent on the net. Box (casilla) `03` (rendimiento neto) is 500.00 and
box `04` (the instalment) is 100.00. Box `19` (the final result) is
0.00 because the minoración for low net income, box `13` (100.00),
absorbs the whole instalment.

The check reports `completeness_status complete` and
`granted_verificado_completo true` (the sequence above asserts this). `export`
writes the fichero-BOE upload file and reports its checksum. It refuses to
overwrite an existing file unless you add `--replace`; see
[The filing workflow](filing-spine.md).

Enter the calculated figures at the AEAT portal (the checklist is
[File your modelo at the AEAT portal](file-at-aeat.md)), then record
the filing with `aeat app modelo work file` while the filing window is open.
`work file` only records the filing in Cadrumo - it does not submit anything.
That record is what lets the next quarter's carries come from this one.
Finally, read the AEAT receipt with `aeat app modelo reconcile pull` so the
official receipt is on record. Both commands close the sequence above as
examples that are not run.

## Stage 3: the second and third quarters

The year continues; record each quarter's activity as it happens. For the
second quarter, say Ana invoices twice and buys once. Register the purchase
invoice and link it to that expense entry here too, before you calculate. Now
the cumulative behaviour shows itself: the second-quarter draft calculates with
NO `--binding` zeros, taking the carries from the first quarter you recorded as
filed. The sequence below starts from a first quarter recorded as filed, then
runs the whole second quarter through to its export:

```{cli-sequence} irpf-lifecycle-q2
:verify: Confirm the second quarter passes the check with its carries resolved from the filed first quarter.
```

Read the saved calculation and compare it with the first quarter's:

- Box `01` (ingresos) now covers January through June - the records used for `2T`
  are the year to date, not the quarter alone.
- Box `05` (pagos fraccionados anteriores) carries the instalment you paid in the
  first quarter, read from your own recorded filing.
- If an earlier quarter had ended negative, box `15` would offset it here.

If calculate blocks instead with an issue about an earlier period, the first
quarter is not recorded as filed and backed by an AEAT receipt in your records -
go back to stage 2 and record its filing and reconcile it. The tool never invents the missing quarter; a visible blank beats
a guessed zero.

Record this quarter's filing with `aeat app modelo work file` once the July window
opens. That command is shown as an example that is not run because it refuses
outside its filing window, and `reconcile pull` follows it.

The third quarter is the same chain one period later, with `3T` in place of
`2T` throughout. Every quarter after the first is this one rhythm.

## Stage 4: the fourth quarter closes the instalment year

Run the same chain for `4T` in January of the following year, the fourth quarter's
filing window being January 1 to 30. After it is filed, Ana has four instalments
on record; together they are the payments on account the annual declaration will
set against her full-year income.

Check the year's IRPF position at any point:

```{cli-sequence} irpf-lifecycle-position
:verify: Confirm the year's IRPF position and declarations list read back.
```

## Stage 5: the annual Renta declaration

The following spring, the annual Modelo 100 gathers the year. It is annual,
so the period code is `0A`, and the filing year is the income year - the
2026 declaration is prepared and filed in 2027.

Before creating it, confirm the year's records are clean. The preflight of your
records for the annual period runs locally:

```{cli-sequence} irpf-lifecycle-annual-preflight
:verify: Confirm the year's records read back clean for the annual period.
```

The rest of the annual chain uses the four instalments recorded as filed and the
2026 version of the Modelo 100, which is published for the 2027 filing season
after this documentation is built, so those commands are shown as examples that
are not run. `dependencies` lists each filing the declaration folds in, the four
Modelo 130 instalments among them, and whether it is backed by a record of filing
or an AEAT receipt. The declaration assembles itself from four kinds of source:
Ana's profile facts, the year's classified records, the four instalments recorded
as filed (folded in as payments on account), and any carry from an earlier Renta.
Employment or capital income your records cannot know about is supplied as manual
boxes, found with `bindings list --missing`:

```{cli-sequence} irpf-lifecycle-annual
```

How every value arrives, and how to trace any figure to its rule and its
article of law, is the subject of
[Deep dive: how the Renta declaration is assembled](../explanation/how-renta-is-assembled.md).

## What you completed

You carried one taxpayer through a whole IRPF year: a first quarter with explicit
zero carries, three quarters whose carries came from your own recorded filings,
and an annual declaration that folded the instalments into one settlement. Every
figure stayed traceable to the entries and the rules that produced it.

## Next steps

- [The VAT year](iva-lifecycle.md) - the same persona and records, through the VAT
  cycle.
- [Prepare a Modelo 130 IRPF instalment](modelo-130.md) - the
  standalone per-quarter recipe.
- [Prepare the annual Modelo 100 Renta declaration](modelo-100.md)
- [Deep dive: how the Renta declaration is assembled](../explanation/how-renta-is-assembled.md)
- [Diagnose and repair your local setup](troubleshooting.md)
