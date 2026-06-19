# Build your first Modelo 130 filing

This tutorial guides you through preparing a quarterly personal income tax
payment-on-account (Modelo 130) for an example taxpayer. You start from an empty
store and finish with a local fichero-BOE file, a text file that follows the
official Boletín Oficial del Estado (BOE) format.

`aeat` prepares local files for Spanish tax forms. It does not submit them to
the Agencia Estatal de Administración Tributaria (AEAT). You upload the exported
file yourself through the AEAT portal.

The ledger is the local record of your business income and expenses. The filing
target is the modelo, year, and period you prepare.

The CLI prints help, labels, and messages in Spanish. This page keeps the
explanations in English and quotes the real Spanish output you will see.

## Prerequisites

You need:

* A working `aeat` command. If you need to install it, start with
  [Quickstart: produce a modelo file](../how-to/quickstart.md).
* A master-key passphrase. `aeat` encrypts your data with a passphrase. The tool
  prompts for it the first time each command runs. To run the commands without a
  prompt, set the `AEAT_SECRET_PASSPHRASE` environment variable first.

This tutorial creates the taxpayer profile and the transactions for you, so you
do not need any earlier setup.

## Step 1: Create your taxpayer profile

Run:

```bash
aeat config profile create tutorial --quiet --tax-id 12345678Z --name "Ana" --surnames "Garcia Lopez" --activity "consultoria" --activity-start-date 2026-01-01
```

The `--name` and `--surnames` are required: the export step refuses without an
operator name. The `--activity-start-date` marks when the activity began, so
`aeat` does not look for a prior-period filing before your first period.

The sample `--tax-id` has the same shape as a Spanish citizen's NIF (their DNI
number). Use your own NIF, CIF, DNI, or NIE when you create a real profile.

The command identifies `tutorial` as the active profile and points to the next
command:

```
profile	tutorial
estado	creado
active_profile	tutorial
next	aeat app modelo work create
```

## Step 2: Record your transactions

Record one business sale and one business expense for the first quarter of 2026.
Both dates fall inside the period (January to March), so both feed the
calculation.

Record the sale (1000 base + 210 IVA = 1210 gross):

```bash
aeat app ledger add --date 2026-02-10 --amount 1210 --direction INCOMING --description "venta" --classification BUSINESS --taxable-base 1000 --iva-rate 0.21 --iva-amount 210
```

Record the expense (500 base + 105 IVA = 605 gross):

```bash
aeat app ledger add --date 2026-02-11 --amount 605 --direction OUTGOING --description "compra" --classification BUSINESS --category-id material_oficina --taxable-base 500 --iva-rate 0.21 --iva-amount 105
```

The `--amount` is the gross total (taxable base plus IVA). The `--classification
BUSINESS` marks each row reviewed straight away, so you do not classify them in a
separate step. An expense row needs a `--category-id`.

Each command confirms the recorded row:

```
ID	23e9e7bc872308add7b31d12ec824e1f2f368ac7d25c261c00095827d9443147
Fecha	2026-02-10
Importe	1210
Descripción	venta
Estado de revisión	reviewed
```

To list both rows, run:

```bash
aeat app ledger list
```

Your output shows the two reviewed rows. The amounts are absolute magnitudes;
the direction (incoming or outgoing) carries the flow, not the sign:

```
MOVIMIENTOS DEL LIBRO CONTABLE
23e9e7bc	23e9e7bc872308add7b31d12ec824e1f2f368ac7d25c261c00095827d9443147	2026-02-10	1210	venta	reviewed
4909ae1b	4909ae1be59603fa021663514c680be058ae008d1a67e908357151d834831763	2026-02-11	605	compra	reviewed
```

Your transaction IDs (the first column) will differ from these.

## Step 3: Create a draft

Create the Modelo 130 draft for the first quarter of 2026:

```bash
aeat app modelo work create --modelo 130 --year 2026 --period 1T
```

The command returns the visible filing target:

```
modelo	130
filing_year	2026
period	1T
revision_id	2019-y-siguientes
state	borrador
```

`aeat` chooses the rule set for that modelo, year, and period, so you do not
need to choose one.

## Step 4: Calculate your tax figures

Calculate the draft for the same filing target. Modelo 130 is cumulative, so the
first period needs the prior-period inputs set to zero. Pass them as bindings:

```bash
aeat app modelo work calculate --modelo 130 --year 2026 --period 1T --binding modelo-130-resultados-negativos-anteriores=0 --binding modelo-130-pagos-fraccionados-anteriores=0 --binding irpf.previous_year_economic_activity_net_income=0
```

The command saves the draft and prints the key figures. The net result
(rendimiento neto) is 500, the sale base minus the expense base:

```
key_figure	03	500.00	Rendimiento neto
key_figure	04	100.00	Importe del pago fraccionado
key_figure	07	100.00	Resultado parcial apartado I
key_figure	12	100.00	Suma de resultados parciales
key_figure	13	100.00	Minoracion por rendimientos netos
key_figure	19	0.00	Resultado final
```

If calculation reports a missing manual value, prior-period value, or binding,
pause the tutorial and use
[Review and supply calculation inputs](../how-to/review-calculation-values.md)
to inspect the modelo casillas and decide the correct value.

## Step 5: Verify your draft

Verify the current calculation for the same filing:

```bash
aeat app modelo work verify --modelo 130 --year 2026 --period 1T
```

Confirm the output shows the status complete and verification granted:

```
completeness_status	complete
granted_verificado_completo	true
finding_count	1
```

The single finding is a non-blocking advisory: it notes that the prior period
falls before your declared activity-start date and will clear once a live AEAT
censo read corroborates the date. A blocking finding would set
`completeness_status` to `blocked` and stop the export.

## Step 6: Export the file for AEAT

Generate the fichero-BOE file:

```bash
aeat app modelo export --modelo 130 --year 2026 --period 1T --output borrador.boe
```

The command writes the file and prints its path, size, and checksum. The
checksum is a file fingerprint you can use to confirm the file later:

```
output_path	borrador.boe
byte_size	946
file_sha256	c18bad622089b5643f0b1778da58413c40a3ee9607a449d99c4f2c0928ff5e8b
format	fichero-boe
```

This `borrador.boe` file is the local finish line. You now have a valid modelo
file to upload at the AEAT portal.

## Step 7: Upload to the AEAT portal

Upload the file with the tax agency:

1. Log in to the official [Agencia Tributaria Sede Electrónica](https://sede.agenciatributaria.gob.es/).
2. Navigate to the Modelo 130 presentation page.
3. Select the option to submit by file upload (*fichero*).
4. Click **Importar** (Import) and upload your `borrador.boe` file. The form
   boxes (*casillas*) fill automatically with your calculated figures.
5. Review and sign the presentation, then download the receipt PDF
   (*justificante*).

The detailed handoff checklist is in
[Upload your exported modelo at the AEAT portal](../how-to/file-at-aeat.md).

## Step 8: (Optional) Record the filing locally

`aeat` can mark a verified draft as filed in your local store. This step is
optional and only works while the AEAT filing-obligation window for the period
is open. It saves a local marker; it does not submit anything to AEAT.

```bash
aeat app modelo work file --modelo 130 --year 2026 --period 1T
```

If the deadline for the period has already passed, the command refuses and
reminds you that export is the local finish line:

```
Refused. Deadline for modelo=130 period=2026 1T closed on 2026-04-20
  -> Run `aeat app modelo work list`
  abort_code: DEADLINE_PASSED
```

That refusal is expected for a past period and does not undo your exported file.

## What you completed

You started from an empty store, recorded business income and an expense,
calculated and verified a Modelo 130 draft, and exported a valid fichero-BOE
file. You used the visible filing target — modelo, year, and period — for every
step. The command output may also print work-unit and calculation-revision IDs
for audit, replay, and advanced exact addressing.

## Next steps and help

For task-focused procedures, read the [how-to guides](../how-to/index.md). To
understand the advanced filing workspace and revision model, read
[The filing workflow: work units and calculation revisions](../how-to/filing-spine.md).
For the underlying concepts, read [How your records become tax figures](../explanation/from-records-to-figures.md).
For manual casilla values, offsets, and binding mechanics, read
[Review and supply calculation inputs](../how-to/review-calculation-values.md).

If a command stops or the local state looks wrong, use
[Diagnose and repair your local setup](../how-to/troubleshooting.md).
