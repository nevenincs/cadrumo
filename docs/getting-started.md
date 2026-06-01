# Getting started with aeat

This guide takes you from a fresh checkout to a validated, exported modelo draft - a file you upload to the Agencia Estatal de Administración Tributaria (AEAT) yourself. It assumes you have Python 3.13 or newer and the [uv](https://docs.astral.sh/uv/) package manager installed.

By the end, you'll have created an operator profile, built a modelo work unit, calculated and verified a draft, and exported it to disk.

## Install and verify

Install the project's dependencies:

```bash
uv sync
```

Confirm the CLI is available and responds:

```bash
aeat --version
aeat --help
```

`aeat --version` prints a single line, such as `aeat 0.1.0`. `aeat --help` lists the two root command families, `config` and `app`. Each command and subcommand carries its own `--help`.

## Configure your profile

`aeat` runs the tax workflow over an active operator profile. Create one:

```bash
aeat config profile create
```

The command guides you through setup, including your tax identity and region. When it finishes, the profile is active. Confirm it and list any others:

```bash
aeat config profile list
```

To activate a different profile later, switch to it by label:

```bash
aeat config profile switch <label>
```

Each profile is stored in its own bucket directory under the local storage root (by default, `var/storage/buckets/`), with an encrypted database for its records. The [architecture guide](architecture.md) explains what a profile holds.

## Run your first workflow

A modelo filing moves through four steps: create a work unit, calculate a draft, verify it, and export it.

1. Create a work unit for the modelo, year, and period you're filing:

   ```bash
   aeat app modelo work create --modelo 130 --year 2024 --period 1T --revision <revision-id>
   ```

   The command returns a work-unit id. Use `aeat app modelo list` to find the available modelos and `aeat app registry inspect` to find the registry revision for your filing.

2. Calculate the draft. This produces a calculation revision with the computed casilla figures:

   ```bash
   aeat app modelo work calculate <work-unit-id>
   ```

   The command returns a calculation-revision id. Supply input figures with repeated `--casilla <number>=<value>` options where the modelo needs them.

3. Verify the draft against the regulatory schema:

   ```bash
   aeat app modelo work verify <calculation-revision-id>
   ```

   A passing verification moves the revision to a verified-complete state and prints a structured report.

4. Inspect what you've built at any point:

   ```bash
   aeat app modelo work list
   aeat app modelo work status <work-unit-id>
   ```

## Find your exported artifacts

Export the verified revision to a local AEAT-compatible file:

```bash
aeat app modelo export <work-unit-id> --output ./M130-2024-1T.xml
```

The file lands at the path you name in `--output`. The command prints the output path, the byte size, and the file's SHA-256 hash so you can confirm what it wrote. The export runs locally and never contacts AEAT.

This is where `aeat` stops. Uploading the exported file to AEAT is a separate step you perform yourself, through the official channel. `aeat` has no command that files on your behalf.

## Next steps

- [Architecture](architecture.md) - the layering behind these commands and the registry authority flow.
- CLI reference - the full command tree, generated from the commands themselves.
