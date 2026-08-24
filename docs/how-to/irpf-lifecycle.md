# The income-tax year: four instalments and the annual Renta

This page covers one full IRPF year for an example taxpayer: four quarterly
Modelo 130 instalments, each building on the ones before it, closing with
the annual Modelo 100 Renta declaration that gathers the whole year. You
start from an empty store; by the end you have prepared and filed every
IRPF filing the year asks of a self-employed consultant.

Cadrumo (the `aeat` command) prepares local files for Spanish tax forms. It
does not submit them to the Agencia Estatal de Administración Tributaria
(AEAT). For Modelo 130 it writes a local fichero-BOE artefact that you present
through the AEAT portal.

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

Create the profile with `aeat config profile`, as
[Set up your taxpayer profile](profile-setup.md) walks through. The documentation
sandbox provisions its own profile, so this create is shown as a display frame:

```{cli-sequence} irpf-lifecycle-profile
```

The `--name` and `--surnames` are required: filing refuses without an
operator name. The `--activity-start-date` marks when the activity began,
so `aeat` does not look for a filing from before your first period. The
sample `--tax-id` has the shape of a Spanish citizen's NIF; use your own
NIF, CIF, DNI, or NIE for a real profile.

Confirm what the year will ask of Ana:

```{cli-sequence} irpf-lifecycle-agenda
:verify: Confirm the year's filing calendar and Modelo 130 applicability read back.
```

The calendar lists the four Modelo 130 windows (April, July, October,
January) and the annual Renta window the following spring. `explain` shows
why Modelo 130 applies: an activity under estimación directa.

## Stage 2: the first quarter

Record the first quarter's activity - one sale, one expense. The `--amount`
is the gross total (taxable base plus IVA), and an expense row needs a
`--category-id` (list the valid ids with `aeat app ledger categories`).

Register the supplier's invoice for that expense, and link it to the expense
row before you calculate. An expense row that claims deductible IVA cannot be
filed without its invoice. A draft bundles its evidence at the
moment you verify it, so an invoice linked after that never reaches the
filing. The invoice registration and the two `ledger add` commands appear as
the collapsed preparation of the sequence below.

Create and calculate the first instalment. Modelo 130 is cumulative, and a
true first period has no history, so the three prior-period carries are
passed as zeros - this is the only quarter where you do this. The sequence
below records the quarter's two rows, creates and calculates the draft,
verifies it, and exports it; the file and reconcile commands
that close the quarter are shown after it:

```{cli-sequence} irpf-lifecycle-q1
:verify: Confirm the first instalment verifies and exports locally.
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
`granted_verificado_completo true` (the sequence above asserts this). `export`
writes the fichero-BOE upload artefact and reports its checksum.

Enter the calculated figures at the AEAT portal (the checklist is
[File your modelo at the AEAT portal](file-at-aeat.md)), then record
the filing locally with `aeat app modelo work file` while the presentation
window is open. `work file` saves a local marker only - it does not submit
anything. The marker is what lets the next quarter's carries resolve from this
one. Finally, pull the justificante with `aeat app modelo reconcile pull` so the
official receipt is on record. Both commands (file, reconcile pull) are shown
after the refusal in the sequence above.

## Stage 3: the second and third quarters

The year continues; record each quarter's activity as it happens. For the
second quarter, say Ana invoices twice and buys once. Link the purchase
invoice to that expense row here too, before you calculate. Now the cumulative
behaviour shows itself: the second-quarter draft calculates with NO `--binding`
zeros, resolving the carries from the filed first quarter. The sequence below
prepares and files that first quarter in its collapsed preparation, then runs
the whole second quarter through to its filed marker:

```{cli-sequence} irpf-lifecycle-q2
:verify: Confirm the second quarter verifies with its carries resolved from the filed first quarter.
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

Record this quarter's filing with `aeat app modelo work file` once the July
window opens. That command is shown as a display frame because it refuses
outside its presentation window, and `reconcile pull` follows it.

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
```

## Stage 5: the annual Renta declaration

The following spring, the annual Modelo 100 gathers the year. It is annual,
so the period token is `0A`, and the filing year is the income year - the
2026 declaration is prepared and filed in 2027.

Before creating it, confirm the year's records are clean. The ledger preflight
for the annual period runs locally:

```{cli-sequence} irpf-lifecycle-annual-preflight
:verify: Confirm the year's ledger reads back clean for the annual period.
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
