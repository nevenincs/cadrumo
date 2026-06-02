# Import and classify a bank statement

Bring your bank records into the ledger and classify them, so a modelo can
calculate from them. You need `aeat` installed and an active
profile; to create one, see [Set up your taxpayer profile](profile-setup.md).
Everything here is local and never contacts the Agencia Estatal de
Administración Tributaria (AEAT).

## Import the statement

Import a statement file, or a directory of them, with `aeat app ledger import`.
Preview first with `--dry-run`, which saves nothing:

```
aeat app ledger import ./statement.csv --provider auto --dry-run
```

`--provider auto` detects the format. When auto-detection guesses wrong, name the
format explicitly, such as `csv`, `ofx`, `qfx`, `xlsx`, `n26`, and `pdf`. When
the preview looks right, run it again without `--dry-run` to save the rows. Add
`--verify` to check the imported entries against the source file. The
[CLI reference](../cli/index.rst) lists every provider and flag.

## Classify the transactions

Imported rows need a tax category before a modelo can read them. Assign one with
`aeat app ledger classify`. To see the accepted category ids, run:

```
aeat app ledger categories
```

Income is classified by direction, so incoming transactions need no category.
Where a transaction mixes business and personal use, record the split with
`aeat app ledger allocate`.

## Check the ledger is ready

Before you calculate a modelo, confirm the period is complete:

```
aeat app ledger preflight --period 2024-01
```

`preflight` reports rows with missing data - a category, a base amount, an IVA
rate, a currency, or a prorrata reference. Fix the flagged rows, then run it
again. To review what you've imported, run `aeat app ledger list` or
`aeat app ledger status`.

## Where next

- [Quickstart](quickstart.md) - calculate and export a modelo from the ready
  ledger.
- [Tutorial](../tutorials/index.md) - the full workflow, end to end.
- [Common filing recipes](index.md) - other modelos and tasks.
- [CLI reference](../cli/index.rst) - every import flag, provider, and exit code.
- [Glossary](../glossary.md) - the Spanish terms used here.
- Report a problem on the [issue tracker](https://github.com/wgergely/aeat/issues).
