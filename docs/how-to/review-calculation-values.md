# Review and supply calculation inputs

Use this guide when calculation reports missing values, when you need to review
which casillas were filled, or when a modelo needs manual inputs, offsets, or
binding values.

Keep this separate from the first Quickstart path. Most ordinary work should be:
set up the active profile, import and classify transactions, create a draft,
calculate, verify, and export. Manual calculation inputs are for the cases where
the modelo cannot derive every value from the profile and ledger.

## How calculation fills a modelo

Calculation combines:

- the active profile facts
- the saved, classified ledger for that profile
- modelo registry casillas, bindings, and formulas
- explicit manual inputs or offsets where the modelo requires them

The result is saved as a new calculation revision. Re-running calculation saves
another revision; it does not mutate the previous revision.

## Inspect the modelo before entering values

Describe the modelo and available revisions:

```bash
aeat app modelo describe 130 --period 2026Q1
```

List casillas:

```bash
aeat app modelo casillas 130 --period 2026Q1
```

Show only required manual casillas:

```bash
aeat app modelo casillas 130 --period 2026Q1 --input-kind manual --required
```

The `casillas` command shows the registry casilla id, printed form number,
input kind, required flag, and label. Use this before providing any
`--casilla` value so you know what the number means.

Inspect formulas and their legal/source references:

```bash
aeat app modelo formulas 130 --period 2026Q1 --explain
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

Use `--casilla CASILLA=DECIMAL` only when the modelo expects an operator-supplied
casilla value or you are intentionally doing a manual correction workflow.
`CASILLA` can be the registry casilla id, record number, or printed BOE casilla
number shown by `aeat app modelo casillas`.

Example after checking the casilla list:

```bash
aeat app modelo work calculate --modelo 130 --year 2026 --period 1T --casilla 02=4000.00
```

Do not use `--casilla NUMBER=VALUE` as a blind placeholder. First list the
casillas and read the labels so you know which field you are filling.

## Understand bindings

A binding is the registry mechanism that connects a modelo field to a source.
Sources can include profile facts, ledger aggregates, prior filed revisions,
live observations, constants, or explicit operator input.

List bindings for a target:

```bash
aeat app modelo bindings list --modelo 130 --year 2026 --period 1T
```

Show only bindings not already resolved by constants or the active profile:

```bash
aeat app modelo bindings list --modelo 130 --year 2026 --period 1T --missing
```

Preview temporary binding values without mutating state:

```bash
aeat app modelo bindings preview --modelo 130 --year 2026 --period 1T --binding irpf.previous_year_economic_activity_net_income=0
```

Provide binding values during calculation only when the binding list shows that
the value cannot be resolved from the profile, ledger, constants, or saved
history:

```bash
aeat app modelo work calculate --modelo 130 --year 2026 --period 1T --binding irpf.previous_year_economic_activity_net_income=0
```

Bindings exist so the registry can name why a value is needed and where it
should come from. They are not part of the basic first-user path.

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

## Correct an already filed local record

If a real filing was already uploaded and later needs correction, use the
amendment workflow rather than quietly replacing the basic draft:

```bash
aeat app modelo work amend --from-filing-record <filing-record-id> --kind complementaria --reason "corrected value" --set <casilla>=<decimal>
```

The amendment command requires an existing filing record with imported official
evidence. It builds a corrected local declaration; it does not submit anything
to AEAT.

## Where to go next

- [Quickstart: produce a modelo file](quickstart.md)
- [Standard prepare-and-export workflow](filing-spine.md)
- [How to prepare a Modelo 303 quarterly filing](modelo-303.md)
- [How to prepare the annual Modelo 390 summary](modelo-390.md)
- [Review calculations with Google Sheets](review-with-google-sheets.md)
- [CLI reference](../cli/index.rst)
