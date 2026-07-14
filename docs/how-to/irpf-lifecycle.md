# The income-tax year: four instalments and the annual Renta

This page covers one full IRPF year for an example taxpayer: four quarterly
Modelo 130 instalments, each building on the ones before it, closing with
the annual Modelo 100 Renta declaration that gathers the whole year. You
start from an empty store; by the end you have prepared and exported every
IRPF filing the year asks of a self-employed consultant.

Cadrumo (the `aeat` command) prepares local files for Spanish tax forms. It
does not submit them to the Agencia Estatal de Administración Tributaria
(AEAT). At each filing you upload the exported file yourself through the
AEAT portal.

Meet the persona this run-through follows: Ana García López, a consultant
(*consultoría*) who started her activity on January 1, 2026, invoices her
clients with 21 percent IVA, and buys office material as she goes. The same
persona and the same ledger continue in
[The IVA year](iva-lifecycle.md) - the two run-throughs describe the same
business from two tax angles.

The CLI prints help, labels, and messages in Spanish. This page keeps the
explanations in English and quotes real Spanish output where it shows one.

## Prerequisites

You need a working `aeat` command (see
[Install Cadrumo](../workstation-setup.md)) and a master-key
passphrase. `aeat` encrypts your data with a passphrase and prompts for it
the first time each command runs.

## Stage 1: set up the taxpayer

Create the profile:

```bash
aeat config profile create ana --quiet --tax-id 12345678Z --name "Ana" --surnames "Garcia Lopez" --activity "consultoria" --activity-start-date 2026-01-01
```

The `--name` and `--surnames` are required: the export step refuses without
an operator name. The `--activity-start-date` marks when the activity began,
so `aeat` does not look for a filing from before your first period. The
sample `--tax-id` has the shape of a Spanish citizen's NIF; use your own
NIF, CIF, DNI, or NIE for a real profile.

Confirm what the year will ask of Ana:

```bash
aeat app overview calendar --from 2026-01-01 --to 2026-12-31 --allow-incomplete
aeat app overview explain 130 --year 2026
```

The calendar lists the four Modelo 130 windows (April, July, October,
January) and the annual Renta window the following spring. `explain` shows
why Modelo 130 applies: an activity under estimación directa.

## Stage 2: the first quarter

Record the first quarter's activity - one sale, one expense. The `--amount`
is the gross total (taxable base plus IVA), and an expense row needs a
`--category-id` (list the valid ids with `aeat app ledger categories`):

```bash
aeat app ledger add --date 2026-02-10 --amount 1210 --direction INCOMING --description "venta" --classification BUSINESS --taxable-base 1000 --iva-rate 0.21 --iva-amount 210
aeat app ledger add --date 2026-02-11 --amount 605 --direction OUTGOING --description "compra" --classification BUSINESS --category-id material_oficina --taxable-base 500 --iva-rate 0.21 --iva-amount 105
```

Create and calculate the first instalment. Modelo 130 is cumulative, and a
true first period has no history, so the three prior-period carries are
passed as zeros - this is the only quarter where you do this:

```bash
aeat app modelo work create --modelo 130 --year 2026 --period 1T
aeat app modelo work calculate --modelo 130 --year 2026 --period 1T --binding modelo-130-resultados-negativos-anteriores=0 --binding modelo-130-pagos-fraccionados-anteriores=0 --binding irpf.previous_year_economic_activity_net_income=0
```

The key figures show the year so far: 1000 earned, 500 spent, and an
instalment of 20 percent on the net:

```
key_figure	03	500.00	Rendimiento neto
key_figure	04	100.00	Importe del pago fraccionado
key_figure	19	0.00	Resultado final
```

(The final result is 0.00 here because the minoración for low net income
absorbs the whole instalment - casilla 13 in the output shows it.)

Verify and export:

```bash
aeat app modelo work verify --modelo 130 --year 2026 --period 1T
aeat app modelo export --modelo 130 --year 2026 --period 1T --output ./modelo-130-2026-1T.boe
```

Verify reports `completeness_status complete` and
`granted_verificado_completo true`. Export writes the fichero-BOE file and
prints its path, size, and SHA-256 checksum - note the checksum; it
identifies exactly which file you upload.

Upload the file at the AEAT portal (the checklist is
[Upload your exported modelo at the AEAT portal](file-at-aeat.md)),
then record the filing locally while the presentation window is open:

```bash
aeat app modelo work file --modelo 130 --year 2026 --period 1T
```

`work file` saves a local marker only - it does not submit anything. The
marker is what lets the next quarter's carries resolve from this one.
Finally, pull the justificante so the official receipt is on record:

```bash
aeat app modelo reconcile pull --modelo 130 --year 2026 --period 1T
```

## Stage 3: the second and third quarters

The year continues; record each quarter's activity as it happens. For the
second quarter, say Ana invoices twice and buys once:

```bash
aeat app ledger add --date 2026-04-15 --amount 2420 --direction INCOMING --description "proyecto abril" --classification BUSINESS --taxable-base 2000 --iva-rate 0.21 --iva-amount 420
aeat app ledger add --date 2026-05-20 --amount 1210 --direction INCOMING --description "proyecto mayo" --classification BUSINESS --taxable-base 1000 --iva-rate 0.21 --iva-amount 210
aeat app ledger add --date 2026-06-05 --amount 302.50 --direction OUTGOING --description "material" --classification BUSINESS --category-id material_oficina --taxable-base 250 --iva-rate 0.21 --iva-amount 52.50
```

Now the cumulative behaviour shows itself. Calculate the second instalment
with NO `--binding` zeros - the carries resolve from the filed first
quarter:

```bash
aeat app modelo work create --modelo 130 --year 2026 --period 2T
aeat app modelo work calculate --modelo 130 --year 2026 --period 2T
```

Read the revision and compare it with the first quarter's:

- Casilla `01` (ingresos) now covers January through June - the ledger
  window for `2T` is the year to date, not the quarter alone.
- Casilla `05` (pagos fraccionados anteriores) carries the instalment you
  paid in the first quarter, read from your own filed record.
- If an earlier quarter had ended negative, casilla `15` would offset it
  here.

If calculate blocks instead with a cross-period finding, the first quarter
is not filed and evidenced on your record - go back to stage 2's `work file`
and `reconcile pull`. The tool never invents the missing quarter; a visible
blank beats a guessed zero.

Verify, export, upload, file, and reconcile exactly as in stage 2:

```bash
aeat app modelo work verify --modelo 130 --year 2026 --period 2T
aeat app modelo export --modelo 130 --year 2026 --period 2T --output ./modelo-130-2026-2T.boe
aeat app modelo work file --modelo 130 --year 2026 --period 2T
aeat app modelo reconcile pull --modelo 130 --year 2026 --period 2T
```

The third quarter is the same loop: record the activity, create and
calculate `--period 3T` (no binding zeros), verify, export, upload, file,
reconcile. Every quarter after the first is this one rhythm.

## Stage 4: the fourth quarter closes the instalment year

Run the same loop for `--period 4T` in January of the following year - the
fourth quarter's presentation window is January 1 to 30. After it is filed,
Ana has four instalments on record; together they are the payments on
account the annual declaration will set against her full-year income.

Check the year's IRPF position at any point:

```bash
aeat app overview status
aeat app modelo work list
```

## Stage 5: the annual Renta declaration

The following spring, the annual Modelo 100 gathers the year. It is annual,
so the period token is `0A`, and the filing year is the income year - the
2026 declaration is prepared and filed in 2027.

Before creating it, confirm the year's records and dependencies are clean:

```bash
aeat app ledger preflight --year 2026 --period 0A
aeat app modelo work dependencies --modelo 100 --year 2026 --period 0A
```

`dependencies` lists each filing the declaration folds in - the four Modelo
130 instalments among them - and whether its evidence is satisfied. A
dependency that does not apply to Ana (a retención model she never files) is
shown as scoped out, not silently skipped.

Create and calculate:

```bash
aeat app modelo work create --modelo 100 --year 2026 --period 0A
aeat app modelo work calculate --modelo 100 --year 2026 --period 0A
```

The declaration assembles itself from four kinds of source: Ana's profile
facts, the year's classified ledger, the four filed instalments (folded in
as payments on account), and any carry from an earlier Renta. Employment or
capital income the ledger cannot know about is supplied as manual casillas -
find what is still missing with:

```bash
aeat app modelo bindings list --modelo 100 --year 2026 --period 0A --missing
```

How every value arrives, and how to trace any figure to its rule and its
article of law, is the subject of
[Deep dive: how the Renta declaration is assembled](../explanation/how-renta-is-assembled.md).

Verify, export, upload, file, and reconcile - the same five moves that
closed every quarter close the year:

```bash
aeat app modelo work verify --modelo 100 --year 2026 --period 0A
aeat app modelo export --modelo 100 --year 2026 --period 0A --output ./modelo-100-2026-0A.boe
aeat app modelo work file --modelo 100 --year 2026 --period 0A
aeat app modelo reconcile pull --modelo 100 --year 2026 --period 0A
```

## What you completed

You carried one taxpayer through a whole IRPF year: a first quarter with
explicit zero carries, three quarters whose carries resolved from your own
filed records, and an annual declaration that folded the instalments into
one settlement. Every figure stayed traceable to the ledger rows and the
rules that produced it.

## Next steps

- [The IVA year](iva-lifecycle.md) - the same persona and ledger, through
  the IVA cycle.
- [Prepare a Modelo 130 IRPF instalment](modelo-130.md) - the
  standalone per-quarter recipe.
- [Prepare the annual Modelo 100 Renta declaration](modelo-100.md)
- [Deep dive: how the Renta declaration is assembled](../explanation/how-renta-is-assembled.md)
- [Diagnose and repair your local setup](troubleshooting.md)
