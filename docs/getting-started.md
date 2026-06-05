# Get started with aeat

`aeat` helps you prepare local files for Spanish tax forms. It checks your
figures, exports a file, and lets you compare the final AEAT receipt with your
local records.

`aeat` does not submit filings to the Agencia Estatal de Administración
Tributaria (AEAT). You upload any exported file yourself through the AEAT
portal.

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
- **Tax identifier**: The identifier `aeat` stores for the taxpayer. Spanish
  citizens usually use their Documento Nacional de Identidad (DNI), foreign
  individuals use their Número de Identidad de Extranjero (NIE), and companies
  or other legal entities use their Número de Identificación Fiscal (NIF) or
  Código de Identificación Fiscal (CIF).
- **Fichero-BOE**: A text file that follows the official Boletín Oficial del
  Estado (BOE) layout and can be uploaded to the AEAT portal.
- **Filing target**: The modelo, year, and period you are preparing.
- **Draft calculation**: The saved set of figures `aeat` calculates for that
  filing target.

## 1. Create your profile

`aeat` stores taxpayer identity, local ledger data, and filing history in a
profile. Create your first profile:

```bash
uv run aeat config profile create my-profile
```

The application prompts for your tax identifier, name, surnames, and tax
region. When the command finishes, this profile becomes active.

## 2. Create your first filing

This example creates Modelo 130 for the first quarter of 2024:

```bash
uv run aeat app modelo work create --modelo 130 --year 2024 --period 1T
```

The command creates or reuses the local workspace for that filing target. Ignore
printed internal IDs while following this guide.

## 3. Calculate the figures

Calculate by repeating the same modelo, year, and period:

```bash
uv run aeat app modelo work calculate --modelo 130 --year 2024 --period 1T
```

The command prints the calculated casillas and saves the draft for the same
filing target. If you run calculation again, `aeat` keeps the earlier draft and
saves the new one too.

If the calculation reports missing figures, supply them with repeatable
`--casilla NUMBER=VALUE` or `--binding KEY=VALUE` flags.

## 4. Verify the draft

Verify the current calculation for the filing:

```bash
uv run aeat app modelo work verify --modelo 130 --year 2024 --period 1T
```

The tool runs the completeness checks and marks the selected draft as verified
when it passes.

## 5. Export the filing

Export the verified filing to a local file:

```bash
uv run aeat app modelo export --modelo 130 --year 2024 --period 1T --output ./modelo-130-2024-1T.boe
```

The command writes the fichero-BOE file and prints the file location, size, and
a SHA-256 checksum. The checksum is a file fingerprint you can use to check the
file later.

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
- To understand the advanced filing workspace and revision model, read
  [How filings, work units, and calculation revisions fit
  together](how-to/filing-spine.md).
- For every flag, including exact work-unit and calculation-revision ID options,
  see the [command reference](cli/index.rst).
- If a command stops or the local state looks wrong, use
  [Diagnose and repair your local setup](how-to/troubleshooting.md).
