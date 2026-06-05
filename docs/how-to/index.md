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

:::{grid-item-card} Filing Calendar
:link: filing-calendar
:link-type: doc

See what may be due and why a modelo applies.
:::

:::{grid-item-card} Transaction Data
:link: import-bank-statements
:link-type: doc

Import, add, edit, remove, and review ledger rows.
:::

:::{grid-item-card} Classify Transactions
:link: classify-transactions
:link-type: doc

Classify rows manually, in bulk, with allocation, or with LLM assistance.
:::

:::{grid-item-card} Calculation Inputs
:link: review-calculation-values
:link-type: doc

Review casillas, missing values, offsets, bindings, and revisions.
:::

:::{grid-item-card} Reconcile a Filing
:link: reconcile
:link-type: doc

Compare local filing data with the AEAT justificante.
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
authenticate-with-aeat
censo-update
filing-calendar
import-bank-statements
classify-transactions
classify-with-llm
review-calculation-values
filing-spine
modelo-303
modelo-390
reconcile
troubleshooting
```
