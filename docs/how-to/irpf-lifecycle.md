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

Create the profile with `aeat config profile create ana --quiet --tax-id
12345678Z --name "Ana" --surnames "Garcia Lopez" --activity "consultoria"
--activity-start-date 2026-01-01`.

The `--name` and `--surnames` are required: the export step refuses without
an operator name. The `--activity-start-date` marks when the activity began,
so `aeat` does not look for a filing from before your first period. The
sample `--tax-id` has the shape of a Spanish citizen's NIF; use your own
NIF, CIF, DNI, or NIE for a real profile.

Confirm what the year will ask of Ana:

```{cli-sequence} irpf-lifecycle-agenda
:verify: Confirm the year's filing calendar and Modelo 130 applicability read back.
@setup aeat config profile edit docs-sequence-sandbox --quiet --accept-defaults --activity-start-date 2026-01-01 --irpf-income-categories actividad_economica
@step Show the year's filing calendar.
aeat --format json app overview calendar --from 2026-01-01 --to 2026-12-31 --allow-incomplete
@step Explain why Modelo 130 applies this year.
@result aeat --format json app overview explain 130 --year 2026
@expect exit_code == 0
```

The calendar lists the four Modelo 130 windows (April, July, October,
January) and the annual Renta window the following spring. `explain` shows
why Modelo 130 applies: an activity under estimación directa.

## Stage 2: the first quarter

Record the first quarter's activity - one sale, one expense. The `--amount`
is the gross total (taxable base plus IVA), and an expense row needs a
`--category-id` (list the valid ids with `aeat app ledger categories`). The two
`ledger add` commands appear as the collapsed setup of the sequence below.

Create and calculate the first instalment. Modelo 130 is cumulative, and a
true first period has no history, so the three prior-period carries are
passed as zeros - this is the only quarter where you do this. The sequence
below records the quarter's two rows, creates and calculates the draft, and
verifies it; the export, file, and reconcile commands that close the quarter
are shown after the verified result (they run against your own evidenced,
filed history, not the sandbox):

```{cli-sequence} irpf-lifecycle-q1
:verify: Confirm the first instalment verifies before you export it.
@setup aeat config profile edit docs-sequence-sandbox --quiet --accept-defaults --activity-start-date 2026-01-01
@setup aeat app ledger add --date 2026-02-10 --amount 1210 --direction INCOMING --description "venta" --classification BUSINESS --taxable-base 1000 --iva-rate 0.21 --iva-amount 210 --idempotency-key irpf-q1-venta
@setup aeat app ledger add --date 2026-02-11 --amount 605 --direction OUTGOING --description "compra" --classification BUSINESS --category-id material_oficina --taxable-base 500 --iva-rate 0.21 --iva-amount 105 --idempotency-key irpf-q1-compra
@step Create the first instalment draft.
aeat --format json app modelo work create --modelo 130 --year 2026 --period 1T
@step Calculate it with the three first-period carries passed as zeros.
aeat --format json app modelo work calculate --modelo 130 --year 2026 --period 1T --binding modelo-130-resultados-negativos-anteriores=0 --binding modelo-130-pagos-fraccionados-anteriores=0 --binding irpf.previous_year_economic_activity_net_income=0
@expect result.casilla_values.03 == "500.00"
@expect result.casilla_values.04 == "100.00"
@step Verify the instalment before exporting it.
@result aeat --format json app modelo work verify --modelo 130 --year 2026 --period 1T
@expect result.granted_verificado_completo == true
@expect exit_code == 0
@static aeat app modelo export --modelo 130 --year 2026 --period 1T --output ./modelo-130-2026-1T.boe
@static aeat app modelo work file --modelo 130 --year 2026 --period 1T
@static aeat app modelo reconcile pull --modelo 130 --year 2026 --period 1T
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

Verify reports `completeness_status complete` and
`granted_verificado_completo true` (the sequence above asserts this). Export
writes the fichero-BOE file and prints its path, size, and SHA-256 checksum -
note the checksum; it identifies exactly which file you upload.

Upload the file at the AEAT portal (the checklist is
[Upload your exported modelo at the AEAT portal](file-at-aeat.md)), then record
the filing locally with `aeat app modelo work file` while the presentation
window is open. `work file` saves a local marker only - it does not submit
anything. The marker is what lets the next quarter's carries resolve from this
one. Finally, pull the justificante with `aeat app modelo reconcile pull` so the
official receipt is on record. All three commands (export, file, reconcile pull)
are shown after the verified result in the sequence above.

## Stage 3: the second and third quarters

The year continues; record each quarter's activity as it happens. For the
second quarter, say Ana invoices twice and buys once. Now the cumulative
behaviour shows itself: the second-quarter draft calculates with NO `--binding`
zeros, resolving the carries from the filed first quarter. The whole second
quarter runs against Ana's evidenced, filed first-quarter record and inside the
July presentation window, neither of which the frozen documentation sandbox can
reproduce, so the chain is shown as display frames:

```{cli-sequence} irpf-lifecycle-q2
@step Record the second quarter's three movements.
@static aeat app ledger add --date 2026-04-15 --amount 2420 --direction INCOMING --description "proyecto abril" --classification BUSINESS --taxable-base 2000 --iva-rate 0.21 --iva-amount 420
@static aeat app ledger add --date 2026-05-20 --amount 1210 --direction INCOMING --description "proyecto mayo" --classification BUSINESS --taxable-base 1000 --iva-rate 0.21 --iva-amount 210
@static aeat app ledger add --date 2026-06-05 --amount 302.50 --direction OUTGOING --description "material" --classification BUSINESS --category-id material_oficina --taxable-base 250 --iva-rate 0.21 --iva-amount 52.50
@step Create the second-quarter draft.
@static aeat app modelo work create --modelo 130 --year 2026 --period 2T
@step Calculate it with no binding zeros; the carries resolve from the filed first quarter.
@static aeat app modelo work calculate --modelo 130 --year 2026 --period 2T
@step Verify, export, file, and reconcile, exactly as in the first quarter.
@static aeat app modelo work verify --modelo 130 --year 2026 --period 2T
@static aeat app modelo export --modelo 130 --year 2026 --period 2T --output ./modelo-130-2026-2T.boe
@static aeat app modelo work file --modelo 130 --year 2026 --period 2T
@static aeat app modelo reconcile pull --modelo 130 --year 2026 --period 2T
```

Read the revision and compare it with the first quarter's:

- Casilla `01` (ingresos) now covers January through June - the ledger
  window for `2T` is the year to date, not the quarter alone.
- Casilla `05` (pagos fraccionados anteriores) carries the instalment you
  paid in the first quarter, read from your own filed record.
- If an earlier quarter had ended negative, casilla `15` would offset it
  here.

If calculate blocks instead with a cross-period finding, the first quarter
is not filed and evidenced on your record - go back to stage 2 and file and
reconcile it. The tool never invents the missing quarter; a visible blank beats
a guessed zero.

The third quarter is the same chain one period later, with `3T` in place of
`2T` throughout. Every quarter after the first is this one rhythm.

## Stage 4: the fourth quarter closes the instalment year

Run the same chain for `4T` in January of the following year, the fourth
quarter's presentation window being January 1 to 30. After it is filed,
Ana has four instalments on record; together they are the payments on
account the annual declaration will set against her full-year income.

Check the year's IRPF position at any point:

```{cli-sequence} irpf-lifecycle-position
:verify: Confirm the year's IRPF position and work-unit list read back.
@step Show the year's overall obligation status.
aeat --format json app overview status
@step List the modelo work units on record.
@result aeat --format json app modelo work list
@expect exit_code == 0
```

## Stage 5: the annual Renta declaration

The following spring, the annual Modelo 100 gathers the year. It is annual,
so the period token is `0A`, and the filing year is the income year - the
2026 declaration is prepared and filed in 2027.

Before creating it, confirm the year's records are clean. The ledger preflight
for the annual period runs locally:

```{cli-sequence} irpf-lifecycle-annual-preflight
:verify: Confirm the year's ledger reads back clean for the annual period.
@setup aeat config profile edit docs-sequence-sandbox --quiet --accept-defaults --activity-start-date 2026-01-01 --irpf-income-categories actividad_economica
@setup aeat app ledger import fixtures/movimientos-2026-1t.csv --provider csv
@step Run the annual-period ledger preflight.
@result aeat --format json app ledger preflight --year 2026 --period 0A
@expect exit_code == 0
```

The rest of the annual chain resolves the four filed instalments and the 2026
Modelo 100 registry revision, which is published for the 2027 filing season
after this documentation is built, so those commands are shown as display
frames. `dependencies` lists each filing the declaration folds in, the four
Modelo 130 instalments among them, and whether its evidence is satisfied. The
declaration assembles itself from four kinds of source: Ana's profile facts, the
year's classified ledger, the four filed instalments (folded in as payments on
account), and any carry from an earlier Renta. Employment or capital income the
ledger cannot know about is supplied as manual casillas, found with `bindings
list --missing`:

```{cli-sequence} irpf-lifecycle-annual
@step Confirm each dependency's evidence is satisfied.
@static aeat app modelo work dependencies --modelo 100 --year 2026 --period 0A
@step Create and calculate the annual declaration.
@static aeat app modelo work create --modelo 100 --year 2026 --period 0A
@static aeat app modelo work calculate --modelo 100 --year 2026 --period 0A
@step Find any manual casillas still missing.
@static aeat app modelo bindings list --modelo 100 --year 2026 --period 0A --missing
@step Verify, export, file, and reconcile, the same five moves that closed every quarter.
@static aeat app modelo work verify --modelo 100 --year 2026 --period 0A
@static aeat app modelo export --modelo 100 --year 2026 --period 0A --output ./modelo-100-2026.boe
@static aeat app modelo work file --modelo 100 --year 2026 --period 0A
@static aeat app modelo reconcile pull --modelo 100 --year 2026 --period 0A
```

How every value arrives, and how to trace any figure to its rule and its
article of law, is the subject of
[Deep dive: how the Renta declaration is assembled](../explanation/how-renta-is-assembled.md).

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
