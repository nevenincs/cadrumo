# aeat-cli

`aeat` is a helper for preparing your Spanish tax forms.

This documentation is the landing page for the `aeat` command-line application:
it shows how to turn local records into checked modelo figures and export files
ready to submit to the Agencia Estatal de Administración Tributaria (AEAT). The
project source is on [GitHub](https://github.com/wgergely/aeat).

`aeat` is for autónomos, small businesses, and the people who help them prepare
Spanish filing records. You prepare one taxpayer's records at a time. The
project is pre-alpha, so expect breaking changes between versions.

The guides on this page are ordered by the usual filing path. Start at the
first thing you have not done yet: install the CLI, set up the taxpayer, prepare
records, decide what is due, produce an export, or follow the full filing loop.

```{important}
`aeat` is not tax advice, is not affiliated with AEAT, and does not replace
AEAT's official tools or professional advice. It builds, checks, and exports
files locally. You file through official AEAT channels yourself and remain
responsible for every declaration you submit. Read the [full disclaimer](disclaimer.md)
before you rely on `aeat`.
```

## Where to Start

::::{grid} 1 2 2 4
:gutter: 3
:class-container: aeat-route-grid

:::{grid-item-card} Start From Scratch
:link: how-to/quickstart
:link-type: doc
:class-card: aeat-route-card

Use this when you are new to `aeat` and want the shortest path through profile,
transactions, calculation, verification, and local export.
:::

:::{grid-item-card} Set Up Your Taxpayer Profile
:link: how-to/profile-setup
:link-type: doc
:class-card: aeat-route-card

Use this when `aeat` does not yet know which taxpayer, activity, or local
profile to use.
:::

:::{grid-item-card} Import Bank Records
:link: how-to/import-bank-statements
:link-type: doc
:class-card: aeat-route-card

Use this when records are not yet in the ledger or still need review.
:::

:::{grid-item-card} Classify Transactions
:link: how-to/classify-transactions
:link-type: doc
:class-card: aeat-route-card

Use this when imported rows need business, personal, mixed-use, category, or
tax-field decisions.
:::

:::{grid-item-card} Plan Your Filing Calendar
:link: how-to/filing-calendar
:link-type: doc
:class-card: aeat-route-card

Use this when you need to see which modelos are due and which period to prepare.
:::

:::{grid-item-card} Follow the Filing Workflow
:link: how-to/filing-spine
:link-type: doc
:class-card: aeat-route-card

Use this when you want the full repeatable loop: prepare, verify, export, file
through AEAT, and keep local history.
:::

:::{grid-item-card} Example Filing Walkthrough
:link: tutorials/index
:link-type: doc
:class-card: aeat-route-card

Build your first Modelo 130 filing from setup through the final local export.
:::

::::

## Go Straight to Usage and Reference

Already know the workflow? Use the [how-to guide index](how-to/index.md) for
task paths, find the comprehensive [command-line reference](cli/index.rst) for
exact commands and options, or read [how it works](explanation/index.md) to see
how taxpayer details and records become modelo figures, what checks run, and
how official rule sources are tracked.

```{toctree}
:hidden:
:caption: Where to start

how-to/quickstart
tutorials/index
```

```{toctree}
:hidden:
:caption: Everyday use

how-to/index
how-to/profile-setup
how-to/authenticate-with-aeat
how-to/censo-update
how-to/import-bank-statements
how-to/classify-transactions
how-to/classify-with-llm
how-to/review-calculation-values
how-to/filing-calendar
how-to/filing-spine
how-to/modelo-303
how-to/modelo-390
how-to/reconcile
how-to/troubleshooting
cli/index
```

```{toctree}
:hidden:
:caption: How it works

explanation/index
```

```{toctree}
:hidden:
:caption: Project

updates
glossary
disclaimer
architecture
authoring-guide
api/aeat
```
