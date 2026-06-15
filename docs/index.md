# aeat-cli

`aeat` is a helper for preparing your Spanish tax forms.

This is the landing page for the `aeat` command-line application. It shows how to
turn local records into checked modelo figures and export files. You upload those
files yourself to the Agencia Estatal de Administración Tributaria (AEAT). The
project source is on [GitHub](https://github.com/wgergely/aeat).

`aeat` is for autónomos, small businesses, and the people who help them prepare
Spanish filing records. You prepare one taxpayer's records at a time. The
project is pre-alpha, so expect breaking changes between versions.

The guides on this page are ordered by the usual filing path. Start at the first
thing you have not done yet. The path runs from installing the CLI and setting up
the taxpayer, through preparing records and deciding what is due, to producing an
export and following the full filing loop.

```{important}
`aeat` is not tax advice, is not affiliated with AEAT, and does not replace
AEAT's official tools or professional advice. It builds, checks, and exports
files locally. You file through official AEAT channels yourself and remain
responsible for every declaration you submit. Read the [full disclaimer](disclaimer.md)
before you rely on `aeat`.
```

## Where to start

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

:::{grid-item-card} Work with Transactions
:link: how-to/import-bank-statements
:link-type: doc
:class-card: aeat-route-card

Use this when records are not yet in the ledger, or when they still need review,
classification, export, split, merge, or evidence links.
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

:::{grid-item-card} Build Your First Modelo 130 Filing
:link: tutorials/index
:link-type: doc
:class-card: aeat-route-card

A guided walkthrough from setup through the final local export.
:::

::::

## Go straight to usage and reference

Already know the workflow? Go straight to the reference you need:

- the [how-to guide index](how-to/index.md) for task paths
- the [command-line reference](cli/index.rst) for exact commands and options
- [how it works](explanation/index.md) for how records become modelo figures,
  what checks run, and how official rule sources are tracked

```{toctree}
:hidden:
:caption: Where to start

how-to/index
tutorials/index
```

```{toctree}
:hidden:
:caption: Everyday use

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
_generated/glossary
disclaimer
architecture/index
authoring-guide
api/aeat
```
