# How-to guides

These guides are short task recipes. Use them when you already know the result
you need: set up a profile, prepare ledger records, calculate a modelo, export a
file, reconcile a receipt, or fix a local problem.

Each guide defines the terms it needs. For exact command options, use the
[command-line reference](../cli/index.rst).

## Setup

- [Set up your taxpayer profile](profile-setup.md): create, switch, and manage
  saved taxpayer identities.
- [Sync your taxpayer census](censo-update.md): read AEAT censo facts, compare
  them with the active profile, and apply the local update when appropriate.
- [Plan your filing calendar](filing-calendar.md): see upcoming deadlines and
  understand why a modelo applies.

## Ledger

- [Import and classify a bank statement](import-bank-statements.md): bring
  transactions into the ledger, classify them, and run preflight before
  calculating.
- [Classify a transaction with an LLM](classify-with-llm.md): ask for a
  classification suggestion, then accept, reject, or override it.

## Prepare and export modelos

- [Quickstart: produce a modelo file](quickstart.md): use the shortest path from
  a ready profile and ledger to an exported file.
- [Standard prepare-and-export workflow](filing-spine.md): prepare a draft,
  check it, export it, and keep a local record.
- [Prepare a quarterly IVA return (Modelo 303)](modelo-303.md): produce a quarterly
  IVA declaration.
- [Produce an annual summary (Modelo 390)](modelo-390.md): produce the annual
  IVA summary.

## Verify, export, upload, and check records

- [Quickstart: produce a modelo file](quickstart.md): verify and export when you
  only need the shortest path.
- [Standard prepare-and-export workflow](filing-spine.md): use this when you need
  the repeated workflow, visible filing targets, current revisions, local file
  markers, and exported files.
- [Reconcile a filing against its justificante](reconcile.md): compare local
  filing data with the receipt issued by the AEAT portal after you upload.

`aeat` does not submit to the AEAT. Exported files are local files. You upload
them yourself through official AEAT channels and keep the justificante for your
records.

## Troubleshooting and support

- [Diagnose and repair your local setup](troubleshooting.md): start with status,
  logs, stored-data checks, active-profile repair, reset guidance, and
  authentication/connectivity checks.

When you ask for help, include the command you ran and redacted output. Do not
paste tax ids, certificate material, full bank details, full justificantes, or
personal documents. Do not paste unredacted log files.

```{toctree}
:hidden:

profile-setup
censo-update
filing-calendar
import-bank-statements
classify-with-llm
quickstart
filing-spine
modelo-303
modelo-390
reconcile
troubleshooting
```
