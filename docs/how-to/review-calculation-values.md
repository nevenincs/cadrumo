# Review and supply calculation inputs

Use this guide when aeat tells you a field is missing after you run a
calculation, or when your form requires a value you must enter by hand — for
example, a prior-year income figure or a compensation amount from an earlier
period.

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

Use `--casilla` only when aeat asks you to supply a specific box value by
hand. Use the box number printed on the official AEAT form — the same number
you see on the paper or PDF version of the modelo. Run
`aeat app modelo casillas 130 --period 1T` to see the list.

Example:

```bash
aeat app modelo work calculate --modelo 130 --year 2026 --period 1T --casilla 02=4000.00
```

Do not enter a box value without checking the list first — read the label so
you know which field you are filling.

## Supply a missing field value

When aeat cannot fill a field automatically, the missing field appears in the
bindings list. Use the list to see which fields need your input, then supply
the value during calculation.

List fields that still need a value:

```bash
aeat app modelo bindings list --modelo 130 --year 2026 --period 1T
```

Show only fields not yet resolved:

```bash
aeat app modelo bindings list --modelo 130 --year 2026 --period 1T --missing
```

Preview what a value would produce — without saving anything:

```bash
aeat app modelo bindings preview --modelo 130 --year 2026 --period 1T --binding irpf.previous_year_economic_activity_net_income=0
```

Supply the value during calculation when the list shows the field cannot be
resolved automatically:

```bash
aeat app modelo work calculate --modelo 130 --year 2026 --period 1T --binding irpf.previous_year_economic_activity_net_income=0
```


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

For registry relation values, calculation accepts repeatable
`--relation KEY=VALUE` inputs. Use them only when the relevant modelo's
registry/help text identifies the relation you need:

```bash
aeat app modelo work calculate --modelo 100 --year 2026 --period 0A --relation <relation-id>=<decimal>
```

## Special calculation tools (IRPF comparison and exemptions)

For specialized calculations, the CLI provides evaluation and comparison commands:

- **Joint vs. individual IRPF comparison (`compare-taxation`)**: Compare filing
  jointly as a family unit against filing individually for an active Modelo 100:
  
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

Before using this command, you must have imported the justificante (the receipt
from AEAT) for the filing you are correcting. The amendment command does not
submit anything to AEAT.

## Where to go next

- [Quickstart: produce a modelo file](quickstart.md)
- [Standard prepare-and-export workflow](filing-spine.md)
- [How to prepare a Modelo 303 quarterly filing](modelo-303.md)
- [How to prepare the annual Modelo 390 summary](modelo-390.md)
- [Review calculations with Google Sheets](review-with-google-sheets.md)
- [CLI reference](../cli/index.rst)
