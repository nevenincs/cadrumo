# Cadrumo

Cadrumo is a helper for preparing your Spanish tax forms.

This is the landing page for Cadrumo and its `aeat` command-line interface (CLI). It shows how to
turn local records into checked modelo figures and export files. You upload those
files yourself to the Agencia Estatal de Administración Tributaria (AEAT). The
project source is on [GitHub](https://github.com/nevenincs/cadrumo).

Cadrumo is for autónomos, small businesses, and the people who help them prepare
Spanish filing records. You prepare one taxpayer's records at a time. The
project is pre-alpha, so expect breaking changes between versions.

The guides on this page are ordered by the usual filing path. Start at the first
thing you have not done yet. The path runs from installing the CLI and setting up
the taxpayer, through preparing records and deciding what is due, to producing an
export and following the full filing loop.

```{important}
Cadrumo is not tax advice, is not affiliated with AEAT, and does not replace
AEAT's official tools or professional advice. It builds, checks, and exports
files locally. You file through official AEAT channels yourself and remain
responsible for every declaration you submit. Read the [full disclaimer](disclaimer.md)
before you rely on Cadrumo.
```

## Where to start

::::{grid} 1 2 2 4
:gutter: 3
:class-container: cadrumo-route-grid

:::{grid-item-card} Start from scratch
:link: how-to/quickstart
:link-type: doc
:class-card: cadrumo-route-card

Use this when you are new to Cadrumo and want the shortest path through profile,
transactions, calculation, verification, and local export.
:::

:::{grid-item-card} Run through the income-tax year
:link: how-to/irpf-lifecycle
:link-type: doc
:class-card: cadrumo-route-card

Use this to follow a worked year of quarterly Modelo 130 instalments closing
with the annual Modelo 100 Renta declaration, command by command.
:::

:::{grid-item-card} Run through the IVA year
:link: how-to/iva-lifecycle
:link-type: doc
:class-card: cadrumo-route-card

Use this to follow a worked year of quarterly Modelo 303 returns, the Modelo
349 branch, and the annual Modelo 390 summary, command by command.
:::

:::{grid-item-card} Set up your taxpayer profile
:link: how-to/profile-setup
:link-type: doc
:class-card: cadrumo-route-card

Use this when Cadrumo does not yet know which taxpayer, activity, or local
profile to use.
:::

:::{grid-item-card} Work with transactions
:link: how-to/import-bank-statements
:link-type: doc
:class-card: cadrumo-route-card

Use this when records are not yet in the ledger, or when they still need review,
classification, export, split, merge, or evidence links.
:::

:::{grid-item-card} Classify transactions
:link: how-to/classify-transactions
:link-type: doc
:class-card: cadrumo-route-card

Use this when imported rows need business, personal, mixed-use, category, or
tax-field decisions.
:::

:::{grid-item-card} Plan your filing calendar
:link: how-to/filing-calendar
:link-type: doc
:class-card: cadrumo-route-card

Use this when you need to see which modelos are due and which period to prepare.
:::

:::{grid-item-card} Prepare your filings
:link: how-to/filing-spine
:link-type: doc
:class-card: cadrumo-route-card

Use this for the repeatable loop - prepare, verify, export, file through
AEAT, reconcile - and the per-modelo recipes: 036, 100 (Renta), 130, 303,
349, and 390.
:::

::::

## Go straight to usage and reference

Already know the workflow? Go straight to the reference you need:

- the [Getting started page](how-to/index.md) for the modelo run-throughs
  and task guides
- the [command-line reference](cli/index.rst) for exact commands and options
- [how it works](explanation/index.md) for how records become modelo figures,
  what checks run, and how official rule sources are tracked

```{toctree}
:hidden:

how-to/index
workstation-setup
```

```{toctree}
:hidden:
:caption: Reference

cli/index
reference/index
_generated/glossary
```

```{toctree}
:hidden:
:caption: How it works

explanation/index
```

```{toctree}
:hidden:
:caption: Help

runbooks/index
disclaimer
```

```{toctree}
:hidden:
:caption: Project

updates
architecture/index
authoring-guide
api/cadrumo
```
