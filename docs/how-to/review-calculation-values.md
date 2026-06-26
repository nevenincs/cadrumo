# Review and supply calculation inputs

Use this guide when aeat tells you a field is missing after you run a
calculation, or when your form requires a value you must enter by hand — for
example, a prior-year income figure or a compensation amount from an earlier
period.

## Before you start

You need:

- A master-key passphrase. `aeat` prompts for it, or you set
  `AEAT_SECRET_PASSPHRASE` for a non-interactive run.
- An active profile. Create one (the `--quiet` form skips the wizard):

  ```bash
  aeat config profile create me --quiet --tax-id 12345678Z --name "Ana" \
    --surnames "Garcia Lopez" --activity "consultoria" --activity-start-date 2026-01-01
  ```

  See [Set up your profile](profile-setup.md) for the full options.
- A work unit for the filing you want to review. Create it before any review or
  calculate command:

  ```bash
  aeat app modelo work create --modelo 130 --year 2026 --period 1T
  ```

## Inspect the modelo before entering values

Describe the modelo and available revisions:

```bash
aeat app modelo describe 130 --period 1T
```

List casillas:

```bash
aeat app modelo casillas 130 --period 1T
```

Show only required manual casillas:

```bash
aeat app modelo casillas 130 --period 1T --input-kind manual --required
```

The `casillas` command shows the registry casilla id, printed form number,
input kind, required flag, and label. Use this before providing any
`--casilla` value so you know what the number means.

Inspect formulas and their legal/source references:

```bash
aeat app modelo formulas 130 --period 1T --explain
```

## Review a saved calculation

These commands read a saved calculation, so run a calculation first. On a fresh
work unit with no calculation yet, they refuse with `work unit has no selectable
current_calculation_revision_id`. Run `aeat app modelo work calculate` (see
[Supply manual casilla values](#supply-manual-casilla-values) below) to produce a
saved draft, then come back here.

List calculation revisions for one filing:

```bash
aeat app modelo work revisions --modelo 130 --year 2026 --period 1T
```

Show the selected or current revision's persisted casilla values:

```bash
aeat app modelo work revision --modelo 130 --year 2026 --period 1T
```

Verify the current draft:

```bash
aeat app modelo work verify --modelo 130 --year 2026 --period 1T
```

Verification output reports whether completeness was granted, how many casillas
were resolved, how many required casillas are missing, and the findings that
block verification. Missing required casillas are values you must resolve before
export.

## Supply manual casilla values

Use `--casilla` only for a box whose input kind is `manual`. Use the box number
printed on the official AEAT form — the same number you see on the paper or PDF
version of the modelo. Run `aeat app modelo casillas 130 --period 1T` to see the
list, and check the `input` column first.

`--casilla` works only on manual boxes. A `bound` box is filled from your ledger
or another source, so `--casilla` refuses it with `cannot override bucket-derived
source-bound casillas` (for example, Modelo 130 box `02` Gastos is `bound`). Fix
the source instead — see [Supply a missing field value](#supply-a-missing-field-value).

A first-period filing also needs its prior-period bindings supplied (record them
as `0` when you have no prior figure). Supply the manual box and the bindings in
the same calculate call. This example sets box `06` (Retenciones e ingresos a
cuenta, a manual box) and seeds the three first-period bindings:

```bash
aeat app modelo work calculate --modelo 130 --year 2026 --period 1T --casilla 06=100.00 \
  --binding modelo-130-resultados-negativos-anteriores=0 \
  --binding modelo-130-pagos-fraccionados-anteriores=0 \
  --binding irpf.previous_year_economic_activity_net_income=0
```

Do not enter a box value without checking the list first — read the label so
you know which field you are filling.

## Supply a missing field value

When aeat cannot fill a field automatically, the missing field appears in the
bindings list. Use the list to see which fields need your input, then supply
the value during calculation.

List every field the modelo binds, with its `source` and a `readiness` label:

```bash
aeat app modelo bindings list --modelo 130 --year 2026 --period 1T
```

Add `--missing` to focus on fields that have no value yet:

```bash
aeat app modelo bindings list --modelo 130 --year 2026 --period 1T --missing
```

Preview what a value would produce — without saving anything:

```bash
aeat app modelo bindings resolve --modelo 130 --year 2026 --period 1T --binding irpf.previous_year_economic_activity_net_income=0
```

Supply the value during calculation when the list shows the field cannot be
resolved automatically:

```bash
aeat app modelo work calculate --modelo 130 --year 2026 --period 1T --binding irpf.previous_year_economic_activity_net_income=0
```


### Where a field's value comes from

The `bindings list` output shows, for each field, a `source` and a `readiness`
label. The `source` tells you who supplies the value; the `readiness` label
restates that source in plain language (for example, `ledger source` or `prior
filed revision`). Use the `source` to decide how to supply the value. The
`source` is one of:

- **Profile fact** - `aeat` fills it from your taxpayer profile, such as
  residence, declaration type, or family composition. Update your profile instead
  of entering the value manually.
- **Ledger source** - `aeat` computes it by summing your classified transactions
  and invoices. You cannot override these; fix the ledger instead.
- **Prior filed revision** - carried forward from an earlier period you already
  filed in `aeat`.
- **Relation** - folded in from another modelo's earlier figures. Supply it with
  `--relation KEY=VALUE` only when the modelo's help names the relation.
- **Manual** - this kind always needs you to type a value, with `--binding
  KEY=VALUE`, or `--casilla` for a box.

A manual field always needs a value you enter by hand. A **prior filed revision**
field also needs one when there is no earlier filing yet to carry it forward —
see the first-time-filing note below. Profile, ledger, and relation fields are
filled for you; correct those at their source rather than typing the value.

If you are filing for the first time and a field asks for a prior-period figure
you do not have, record it as zero, for example `--binding <field-id>=0`. Enter a
real prior figure only when you have one prepared outside `aeat`.

## Handle offsets and carry-forwards

Some modelos need prior-period values, credits, or compensation amounts. Do not
guess these from the current transaction ledger.

For Modelo 303 IVA compensation, inspect or seed the local IVA compensation
wallet:

```bash
aeat app modelo iva-wallet balance --as-of-year 2026
aeat app modelo iva-wallet seed --filing-year 2024 --period 4T --amount 0 --confirm
```

Use `--amount 0` only for a true first Modelo 303 period with no previous IVA
compensation balance. Use a positive amount only when you have the pending
compensation amount from earlier Modelo 303 filings prepared outside this local
history.

Seeding refuses if a record already exists for the period. To fix a wrong
opening amount you seeded earlier, correct it:

```bash
aeat app modelo iva-wallet correct --filing-year 2024 --period 4T --amount 1200.50 --reason "typo in opening balance" --confirm
```

The correction overwrites the seeded amount and records your `--reason` in an
audit event. It refuses when no record exists for the period (seed it first) and
when an already-filed Modelo 303 has consumed the seeded basis — correcting it
then would change a return you have already filed. In that case file a
complementaria instead (see [Correct an already filed local record](#correct-an-already-filed-local-record)).

For registry relation values, calculation accepts repeatable
`--relation KEY=VALUE` inputs. Use them only when the relevant modelo's
registry/help text identifies the relation you need:

```bash
aeat app modelo work calculate --modelo 100 --year 2026 --period 0A --relation <relation-id>=<decimal>
```

## Supply rows for multi-record informativa modelos

Some informational modelos report a list of records rather than one set of boxes:
attribution members (Modelo 184), related-party operations (Modelo 232),
declared counterparties (Modelo 347), and intra-community operators (Modelo 349).
Supply each record with a repeatable `--row` input.

Each `--row` starts with the record type, followed by its fields:

```bash
aeat app modelo work create --modelo 184 --year 2024 --period 0A --revision 2015-y-siguientes
aeat app modelo work calculate <work-unit-id> \
  --row 'miembro nif=45678912S porcentaje=60 importe=10000' \
  --row 'miembro nif=00000001R porcentaje=40 importe=5000'
```

Take `<work-unit-id>` from the `work_unit_id` field that `work create` prints.
For these multi-record modelos, pass the work-unit id as the positional argument
rather than the `--modelo / --year / --period` flags used elsewhere on this page.

Use one of these record types:

- `miembro` - an attribution member (Modelo 184).
- `vinculada` - a related-party operation (Modelo 232).
- `contraparte` - a declared counterparty (Modelo 347).
- `operador` - an intra-community operator (Modelo 349).

`aeat` validates each row against the modelo's rules and refuses an incomplete
set:

- Modelo 184 - the members' `porcentaje` values must sum to 100.
- Modelo 347 - a counterparty's annual total must exceed 3,005.06 euros.
- Modelo 349 - the operator's intra-community NIF must match its country format.

The saved rows appear in the calculation output as `detail_row` lines. Check
them to confirm what was recorded.

## Special calculation tools (IRPF comparison and exemptions)

For specialized calculations, the CLI provides evaluation and comparison commands:

- **Joint vs. individual IRPF comparison (`compare-taxation`)**: Compare filing
  jointly as a family unit against filing individually for an active Modelo 100.
  Create the Modelo 100 draft first (`aeat app modelo work create --modelo 100
  --year 2026 --period 0A`), or the command refuses with `Ninguna unidad de
  trabajo activa`:
  
  ```bash
  aeat app modelo work compare-taxation --modelo 100 --year 2026 --period 0A
  ```
  
  This check does not save a draft. It shows the tax difference and a
  recommendation so you can decide which filing option costs less.

- **Maritime worker exemption preview (`preview-maritime-exemption`)**: Preview
  the IRPF exemption for maritime workers (Art. 7.p LIRPF or REBECA 50%):
  
  ```bash
  aeat app modelo work preview-maritime-exemption
  ```
  
  The command shows which tax boxes are affected by the exemption and the
  amounts, with references to the applicable law. This applies only to maritime
  workers — most filers can skip this section.

## Correct an already filed local record

If a filing was already uploaded and later needs correction, use the amendment
command. Do not simply recalculate the same period — that would not create the
correct complementaria (supplementary return) record:

```bash
aeat app modelo work amend --from-filing-record <filing-record-id> --kind complementaria --reason "corrected value" --set <casilla>=<decimal>
```

Before using this command, you must have imported the {term}`justificante` for the filing you are correcting. The amendment command does not
submit anything to AEAT.

## Where to go next

- [Quickstart: produce a modelo file](quickstart.md)
- [Standard prepare-and-export workflow](filing-spine.md)
- [How to prepare a Modelo 303 quarterly filing](modelo-303.md)
- [How to prepare the annual Modelo 390 summary](modelo-390.md)
- [Review calculations with Google Sheets](review-with-google-sheets.md)
- [CLI reference](../cli/index.rst)
