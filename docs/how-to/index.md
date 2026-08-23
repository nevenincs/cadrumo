# Getting started

This page routes you to the right guide. The guides are grouped the way a
filing year actually runs: set up who the taxpayer is, see what is due and
when, keep the ledger of what happened, and prepare each filing. Cadrumo is
the product; the Agencia Estatal de Administración Tributaria (AEAT) is the
external tax authority, and Cadrumo never submits a return or acts as AEAT -
read
[how records become filing-ready figures](../explanation/from-records-to-figures.md)
for that boundary.

Start with the [installation guide](../workstation-setup.md) if the `aeat`
command does not run. For a map of the whole journey from bank records to a
filed modelo, read [the filing journey](onboarding.md). For terminology, use
the {doc}`glossary </_generated/glossary>`; for exact options and refusals,
the [command-line reference](../cli/index.rst).

For an ordinary failure, follow [Diagnose and repair](troubleshooting.md) and
open a [public issue](https://github.com/nevenincs/cadrumo/issues) with
redacted output if the problem remains. Never publish taxpayer data,
credentials, or a vulnerability in an issue.

## Run through a filing year

Two modelo-based run-throughs carry one example taxpayer through a complete
filing year, command by command. Start here to see the whole workflow before
running your own.

::::{grid} 1 2 2 3
:gutter: 3

:::{grid-item-card} The income-tax year: Modelo 130 → 100
:link: irpf-lifecycle
:link-type: doc

Four quarterly Modelo 130 instalments, each building on the ones before it,
closing with the annual Modelo 100 Renta declaration.
:::

:::{grid-item-card} The IVA year: Modelo 303 → 349 → 390
:link: iva-lifecycle
:link-type: doc

Four quarterly Modelo 303 returns with the IVA credit carrying between them,
a Modelo 349 branch, and the annual Modelo 390 summary.
:::

:::{grid-item-card} Quickstart
:link: quickstart
:link-type: doc

Shortest path from profile and ledger to an exported modelo file: one
modelo, one period, copy-paste commands.
:::

:::{grid-item-card} Your first quarterly filing
:link: first-quarterly-filing
:link-type: doc

First-time walk-through of one Modelo 130 quarter: import a statement,
classify the rows, prepare the draft, and confirm it verifies.
:::

::::

## Your profile

Who the taxpayer is, and the facts that decide what you owe.

::::{grid} 1 2 2 3
:gutter: 3

:::{grid-item-card} Set up your taxpayer profile
:link: profile-setup
:link-type: doc

Create, inspect, export, import, rename, or delete taxpayer profiles, and log
in to the one you want active.
:::

:::{grid-item-card} Authenticate with AEAT
:link: authenticate-with-aeat
:link-type: doc

Configure read-only AEAT authentication for live-read workflows.
:::

:::{grid-item-card} Maintain Modelo 036 census facts
:link: censo-update
:link-type: doc

Keep AEAT census facts correct in the active profile.
:::

:::{grid-item-card} Find out which modelos apply
:link: choose-modelo
:link-type: doc

Ask which modelos apply to you and why, from your saved profile facts.
:::

:::{grid-item-card} Protect access to your data
:link: protect-data-access
:link-type: doc

Store your passphrase safely, log out, or reset local state.
:::

::::

## Your calendar

What is due, and when.

::::{grid} 1 2 2 3
:gutter: 3

:::{grid-item-card} Plan your filing calendar
:link: filing-calendar
:link-type: doc

See what may be due, when filing windows open and close, and which period
tokens address them.
:::

:::{grid-item-card} Read AEAT notifications
:link: check-aeat-notifications
:link-type: doc

Capture official notifications and read live AEAT data, view-only.
:::

:::{grid-item-card} Check that a filing is ready
:link: filing-readiness
:link-type: doc

Check readiness, what a filing depends on, its full history, and
year-over-year changes.
:::

::::

## Your ledger

The record of what happened: bring transactions in, classify them, and keep
the evidence.

::::{grid} 1 2 2 3
:gutter: 3

:::{grid-item-card} Import and manage transactions
:link: import-bank-statements
:link-type: doc

Import, add, edit, remove, and review ledger rows.
:::

:::{grid-item-card} Classify transactions
:link: classify-transactions
:link-type: doc

Classify rows manually, in bulk, with allocation, or through the review queue.
:::

:::{grid-item-card} Classify with an LLM
:link: classify-with-llm
:link-type: doc

Set up a provider, preview and apply suggestions, and classify from an
attached invoice.
:::

:::{grid-item-card} Attach invoices and receipts
:link: ledger-evidence
:link-type: doc

Store invoices and receipts and link them to the transactions they support.
:::

:::{grid-item-card} Manage business invoices
:link: manage-invoices
:link-type: doc

Record issued and received invoices and feed intra-community operations to Modelo 349.
:::

:::{grid-item-card} Correct mistakes in your ledger
:link: correct-ledger-entries
:link-type: doc

Update, remove, split, merge, stash, or archive transactions safely.
:::

:::{grid-item-card} Apply IVA prorrata deductions
:link: prorrata
:link-type: doc

Deduct input IVA under general or especial prorrata and declare differentiated sectors.
:::

::::

## Your filings

The per-modelo work: prepare, review, verify, export, file, and reconcile.

::::{grid} 1 2 2 3
:gutter: 3

:::{grid-item-card} The filing workflow
:link: filing-spine
:link-type: doc

Understand drafts, verification, export, filing markers, and history.
:::

:::{grid-item-card} Modelo 036
:link: modelo-036
:link-type: doc

Record an alta, modificacion, or baja you filed at AEAT's sede.
:::

:::{grid-item-card} Modelo 100 (Renta)
:link: modelo-100
:link-type: doc

Prepare the annual Renta declaration that gathers the whole year.
:::

:::{grid-item-card} Modelo 130
:link: modelo-130
:link-type: doc

Prepare the quarterly IRPF instalment, cumulative across the year.
:::

:::{grid-item-card} Modelo 303
:link: modelo-303
:link-type: doc

Prepare, verify, and export a quarterly IVA return.
:::

:::{grid-item-card} Modelo 349
:link: modelo-349
:link-type: doc

Declare intra-community operations from your invoice records.
:::

:::{grid-item-card} Modelo 390
:link: modelo-390
:link-type: doc

Prepare the annual IVA summary.
:::

:::{grid-item-card} Review calculation inputs
:link: review-calculation-values
:link-type: doc

Review which form boxes were filled, supply missing values, and handle offsets.
:::

:::{grid-item-card} Review with Google Sheets
:link: review-with-google-sheets
:link-type: doc

Export, edit, and pull back modelo calculations using a Google Sheets spreadsheet.
:::

:::{grid-item-card} Verify a filing
:link: verification-reports
:link-type: doc

Run verification, read the report findings, and fix what blocks export.
:::

:::{grid-item-card} File at AEAT
:link: file-at-aeat
:link-type: doc

Export the file, upload it at the AEAT portal yourself, record, and reconcile.
:::

:::{grid-item-card} Reconcile a filing
:link: reconcile
:link-type: doc

Pull and store the AEAT justificante, then compare it with your local filing
record.
:::

::::

## Tools and help

::::{grid} 1 2 2 3
:gutter: 3

:::{grid-item-card} Connect an agent (MCP)
:link: connect-an-agent
:link-type: doc

Expose the toolset to Claude or any MCP client, with the safety boundary intact.
:::

:::{grid-item-card} Troubleshooting
:link: troubleshooting
:link-type: doc

Fix active-profile, storage, registry, and authentication problems.
:::

::::

```{toctree}
:hidden:

onboarding
```
