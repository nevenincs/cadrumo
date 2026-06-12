# How-to guides

Pick the question closest to what you are trying to do. For exact command
options, use the [command-line reference](../cli/index.rst).

## How do I start this?

::::{grid} 1 2 2 3
:gutter: 3

:::{grid-item-card} Quickstart
:link: quickstart
:link-type: doc

Shortest path from profile and ledger to an exported modelo file.
:::

:::{grid-item-card} Set Up a Profile
:link: profile-setup
:link-type: doc

Create, inspect, switch, export, import, rename, or delete taxpayer profiles.
:::

:::{grid-item-card} Authenticate with AEAT
:link: authenticate-with-aeat
:link-type: doc

Configure read-only AEAT authentication for live-read workflows.
:::

::::

## What do I have to do?

::::{grid} 1 2 2 3
:gutter: 3

:::{grid-item-card} Link Modelo 036 Censo
:link: censo-update
:link-type: doc

Pull, compare, and apply AEAT census facts for the active profile.
:::

:::{grid-item-card} Which Modelos Apply to You
:link: choose-modelo
:link-type: doc

Ask which modelos apply to you and why, from your saved profile facts.
:::

:::{grid-item-card} Filing Calendar
:link: filing-calendar
:link-type: doc

See what may be due and when filing windows open and close.
:::

:::{grid-item-card} Filing Periods
:link: filing-periods
:link-type: doc

Understand quarters, annual period codes, dates, and year-end.
:::

:::{grid-item-card} AEAT Notifications
:link: check-aeat-notifications
:link-type: doc

Capture, list, and view official AEAT notifications from your electronic inbox.
:::

:::{grid-item-card} Work with Transactions
:link: import-bank-statements
:link-type: doc

Import, add, edit, remove, and review ledger rows.
:::

:::{grid-item-card} Classify Transactions
:link: classify-transactions
:link-type: doc

Classify rows manually, in bulk, with allocation, or with LLM assistance.
:::

:::{grid-item-card} Attach Invoices and Receipts
:link: ledger-evidence
:link-type: doc

Store invoices and receipts and link them to the transactions they support.
:::

:::{grid-item-card} Correct Ledger Mistakes
:link: correct-ledger-entries
:link-type: doc

Update, remove, split, merge, stash, or archive transactions safely.
:::

:::{grid-item-card} Record Modelo 036
:link: modelo-036
:link-type: doc

Record an alta, modificacion, or baja you filed at AEAT's sede.
:::

:::{grid-item-card} Calculation Inputs
:link: review-calculation-values
:link-type: doc

Review which form boxes were filled, supply missing values, and handle offsets.
:::

:::{grid-item-card} Google Sheets Review
:link: review-with-google-sheets
:link-type: doc

Export, edit, and pull back model calculations using a Google Sheets spreadsheet.
:::

:::{grid-item-card} Verify a Filing
:link: verification-reports
:link-type: doc

Run verification, read the report findings, and fix what blocks export.
:::

:::{grid-item-card} File at AEAT
:link: file-at-aeat
:link-type: doc

Export the file, upload it at the AEAT portal yourself, record, and reconcile.
:::

:::{grid-item-card} Reconcile a Filing
:link: reconcile
:link-type: doc

Compare local filing data with the AEAT justificante.
:::

:::{grid-item-card} Filing Receipts
:link: justificante-receipts
:link-type: doc

Pull, store, and inspect the AEAT justificante for each filed period.
:::

::::

## How does this work?

::::{grid} 1 2 2 3
:gutter: 3

:::{grid-item-card} Filing Workflow
:link: filing-spine
:link-type: doc

Understand drafts, verification, export, filing markers, and history.
:::

:::{grid-item-card} Modelo 303
:link: modelo-303
:link-type: doc

Prepare, verify, and export a quarterly IVA return.
:::

:::{grid-item-card} Modelo 390
:link: modelo-390
:link-type: doc

Prepare the annual IVA summary.
:::

:::{grid-item-card} LLM Classification
:link: classify-with-llm
:link-type: doc

Preview, apply, reject, or override local LLM suggestions.
:::

:::{grid-item-card} LLM Provider Setup
:link: setup-llm-classification
:link-type: doc

Install and authenticate a provider CLI so LLM suggestions work.
:::

:::{grid-item-card} Protect Data Access
:link: protect-data-access
:link-type: doc

Set up a recovery key, change or recover your passphrase, lock, or reset.
:::

:::{grid-item-card} Troubleshooting
:link: troubleshooting
:link-type: doc

Fix active-profile, storage, registry, and authentication problems.
:::

::::

`aeat` does not submit to AEAT. Exported files are local files. You upload them
yourself through official AEAT channels and keep the justificante for your
records.

```{toctree}
:hidden:

quickstart
profile-setup
censo-update
choose-modelo
filing-calendar
filing-periods
check-aeat-notifications
import-bank-statements
classify-transactions
ledger-evidence
correct-ledger-entries
modelo-036
classify-with-llm
setup-llm-classification
review-calculation-values
review-with-google-sheets
filing-spine
modelo-303
modelo-390
verification-reports
file-at-aeat
reconcile
justificante-receipts
protect-data-access
troubleshooting
authenticate-with-aeat
```
