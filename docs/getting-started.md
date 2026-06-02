# Get started with aeat

This guide walks you through your first filing with `aeat`. You'll install the tool and set up a profile. Then you'll build a draft of a modelo (a Spanish tax form), verify it, and export a file. You upload that file to the Agencia Estatal de Administración Tributaria (AEAT) yourself.

## Before you begin

You need:

- Python 3.13 or newer
- The [uv](https://docs.astral.sh/uv/) package manager

Get the source and enter the directory:

```bash
git clone https://github.com/wgergely/aeat
cd aeat
```

## Install aeat

Install the tool, then confirm it runs:

```bash
uv sync
aeat --version
```

The version command prints a single line, such as `aeat 0.1.0`. To list the available commands, run `aeat --help`.

## Create your profile

`aeat` keeps your tax identity and settings in a profile. Create your first one:

```bash
aeat config profile create
```

The command asks for your details, including your tax identity and region. When it finishes, your profile is active.

## Build your first filing

A filing moves through four steps: create, calculate, verify, and export. This example builds Modelo 130, the quarterly income-tax instalment, for the first quarter of 2024. The `1T` period code means the first quarter. Along the way, you'll copy two ids the tool prints: a work-unit id and a calculation-revision id.

First, find the revision for the form. A revision is the rule version a modelo follows. List the revisions the modelo offers:

```bash
aeat app modelo describe --modelo 130
```

The output lists the available revisions, each with an identifier such as `2019-y-siguientes`. Copy the identifier that covers your filing period, then use it wherever the next command shows `<revision>`.

1. Create the work unit, the draft that tracks one modelo for one period:

   ```bash
   aeat app modelo work create --modelo 130 --year 2024 --period 1T --revision <revision>
   ```

   The command prints a work-unit id. Copy it, then use it wherever the next steps show `<work-unit-id>`.

2. Calculate the figures. Calculating fills in the casillas, the numbered fields on the form:

   ```bash
   aeat app modelo work calculate <work-unit-id>
   ```

   The command prints a calculation-revision id. Copy it for the next step. If it reports missing figures, the note at the end of this guide explains how to supply them.

3. Verify the calculation against the tax rules:

   ```bash
   aeat app modelo work verify <calculation-revision-id>
   ```

   `aeat` prints a report and marks the calculation complete.

4. Export the file:

   ```bash
   aeat app modelo export <work-unit-id> --output ./modelo-130-2024-1T.xml
   ```

   `aeat` writes the file to the path you give in `--output`, then prints its location, size, and a content hash.

You now have an exported filing. To list your work units at any point, run `aeat app modelo work list`.

## Upload it yourself

`aeat` stops at the exported file. Upload that file to AEAT yourself, through its electronic filing portal (the sede electrónica).

## Next steps

Now that you've produced a filing:

- Next time, the [quickstart](how-to/quickstart.md) gets you there in four commands.
- The [tutorial](tutorials/index.md) builds a modelo end to end with a worked example.
- The [how-to recipes](how-to/index.md) cover other modelos and tasks: [import a bank statement](how-to/import-bank-statements.md), file 303 or 390, sync the censo, and [diagnose problems](how-to/troubleshooting.md).
- The [explanation](explanation/index.md) covers how the pipeline works and why `aeat` never files.

> **A note on figures.** Some modelos need figures you enter by hand. If a calculation reports missing inputs, add them with repeated `--casilla <number>=<value>` options on the `work calculate` command.
