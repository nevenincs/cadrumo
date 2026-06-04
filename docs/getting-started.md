# Get started with aeat

`aeat` prepares, verifies, exports, and reconciles local Spanish tax filing
artifacts. It does not submit filings to AEAT. You upload any exported file
yourself through the AEAT portal.

This guide walks through installing the command, creating your first taxpayer
profile, drafting a Modelo 130 filing, verifying it, and exporting the local
file.

## Install the command

You need Python 3.13 or newer and [uv](https://docs.astral.sh/uv/).

Clone the repository, install the environment, and confirm the command responds:

```bash
git clone https://github.com/wgergely/aeat
cd aeat
uv sync
uv run aeat --version
```

The version command prints a single line, such as `aeat 0.1.0`.

## Core concepts

Spanish tax reporting uses a few recurring terms:

- **Autónomo**: A self-employed worker, sole proprietor, or freelancer registered
  in Spain.
- **AEAT**: The *Agencia Estatal de Administración Tributaria*, Spain's state tax
  agency.
- **Modelo**: An official tax form, identified by a number. Modelo 130 is the
  quarterly payment-on-account for personal income tax.
- **Casilla**: A numbered box or field on the official form.
- **Fichero-BOE**: A text file that follows the official BOE layout and can be
  uploaded to the AEAT portal.

## 1. Create your profile

`aeat` stores taxpayer identity, local ledger data, and filing history in a
profile. Create your first profile:

```bash
aeat config profile create my-profile
```

The application prompts for your tax identity, name, surnames, and tax region.
When the command finishes, this profile becomes your active workspace.

## 2. Create your first filing

This example creates Modelo 130 for the first quarter of 2024:

```bash
aeat app modelo work create --modelo 130 --year 2024 --period 1T
```

The command creates or reuses the work unit for that visible filing target. You
can ignore printed internal IDs while following this guide.

## 3. Calculate the figures

Calculate by repeating the same modelo, year, and period:

```bash
aeat app modelo work calculate --modelo 130 --year 2024 --period 1T
```

The command prints the calculated casillas and saves a calculation revision under
the same work unit. If you run calculation again, `aeat` keeps another revision
under that same filing target.

If the calculation reports missing figures, supply them with repeatable
`--casilla NUMBER=VALUE` or `--binding KEY=VALUE` flags.

## 4. Verify the draft

Verify the current calculation for the filing:

```bash
aeat app modelo work verify --modelo 130 --year 2024 --period 1T
```

The tool runs the completeness checks and marks the selected calculation revision
as verified when it passes.

## 5. Export the filing

Export the verified filing to a local file:

```bash
aeat app modelo export --modelo 130 --year 2024 --period 1T --output ./modelo-130-2024-1T.boe
```

The command writes the fichero-BOE file and prints the file location, size, and
SHA-256 checksum.

## 6. Upload to the AEAT portal

The final step is manual:

1. Log in to Spain's official AEAT electronic filing portal.
2. Select the option to submit Modelo 130 by file upload.
3. Select and upload `./modelo-130-2024-1T.boe`.
4. Confirm and sign the filing.

## Next steps

- For day-to-day filing tasks, see the [how-to guides](how-to/index.md).
- To practice with sample transaction data, follow the
  [tutorial](tutorials/index.md).
- To understand work units, calculation revisions, and exact-addressing escape
  hatches, read [How filings, work units, and calculation revisions fit
  together](how-to/filing-spine.md).
- For every flag, including exact work-unit and calculation-revision ID options,
  see the [CLI reference](cli/index.rst).
- For terms, read the [glossary](glossary.md).
- Report bugs or ask questions on the
  [issue tracker](https://github.com/wgergely/aeat/issues).
