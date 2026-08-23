# Cadrumo documentation

```{image} _static/index-header.png
:alt: Paper tax forms, an envelope, a keyboard, and a calculator arranged on a desk
:class: cadrumo-index-header
:width: 100%
```

This is the documentation for Cadrumo and its `aeat` command-line interface
(CLI). Cadrumo turns your records into checked modelo figures and an export
file. You upload that file to the Agencia Estatal de Administración Tributaria
(AEAT) yourself. The source is on
[GitHub](https://github.com/nevenincs/cadrumo). Cadrumo is in beta; interfaces
may still change between releases.

```{important}
Cadrumo is not tax advice, is not affiliated with AEAT, and does not replace
AEAT's official tools or advice from a qualified professional. It builds,
checks, and exports files locally. You file through official AEAT channels
yourself and remain responsible for every declaration you submit. Read the
[full disclaimer](disclaimer.md) before you rely on Cadrumo.
```

## Where to start

These guides cover the whole preparation cycle: setting up a taxpayer
profile, importing and classifying bank records, checking what is due, and
preparing, verifying, and exporting each modelo. The two worked years - one
for income tax, one for IVA - walk the full cycle with real commands.

::::{grid} 1 2 2 4
:gutter: 3
:class-container: cadrumo-route-grid

:::{grid-item-card} Start from scratch
:link: how-to/quickstart
:link-type: doc
:class-card: cadrumo-route-card

Take the shortest path from an empty profile to an exported modelo file.
:::

:::{grid-item-card} Run through the income-tax year
:link: how-to/irpf-lifecycle
:link-type: doc
:class-card: cadrumo-route-card

Follow a worked year of Modelo 130 quarters closing into the annual
Modelo 100 Renta declaration, command by command.
:::

:::{grid-item-card} Run through the IVA year
:link: how-to/iva-lifecycle
:link-type: doc
:class-card: cadrumo-route-card

Follow a worked year of Modelo 303 quarters, the Modelo 349 branch, and
the annual Modelo 390 summary, command by command.
:::

:::{grid-item-card} Set up your taxpayer profile
:link: how-to/profile-setup
:link-type: doc
:class-card: cadrumo-route-card

Create the taxpayer profile and record the facts that decide which
modelos apply.
:::

:::{grid-item-card} Import and manage transactions
:link: how-to/import-bank-statements
:link-type: doc
:class-card: cadrumo-route-card

Import bank statements, review the rows, and attach the evidence behind
them.
:::

:::{grid-item-card} Classify transactions
:link: how-to/classify-transactions
:link-type: doc
:class-card: cadrumo-route-card

Decide business, personal, or mixed use and set the category and tax
fields on each row.
:::

:::{grid-item-card} Plan your filing calendar
:link: how-to/filing-calendar
:link-type: doc
:class-card: cadrumo-route-card

See which modelos are due and which period to prepare next.
:::

:::{grid-item-card} Prepare your filings
:link: how-to/filing-spine
:link-type: doc
:class-card: cadrumo-route-card

Prepare, verify, export, file at AEAT, and reconcile - with a recipe per
modelo: 036, 100 (Renta), 130, 303, 349, and 390.
:::

::::

## Search everything

Press {kbd}`Ctrl+K` ({kbd}`Cmd+K` on macOS) on any page to search tax concepts,
casillas, commands, and guides; exact term matches appear first. Use the
[command-line reference](cli/index.rst) for commands and options, and
[how it works](explanation/index.md) for how records become modelo figures and
what checks run. Use [Import, export, and evidence](reference/import-export-and-evidence.md)
to distinguish source data, review outputs, AEAT upload files, official filing
proof, and audit packages.

```{toctree}
:hidden:

Getting started <how-to/index>
Get Cadrumo <download>
Install Cadrumo <workstation-setup>
Quickstart <how-to/quickstart>
First quarterly filing <how-to/first-quarterly-filing>
The income-tax year <how-to/irpf-lifecycle>
The IVA year <how-to/iva-lifecycle>
```

```{toctree}
:hidden:
:caption: Your profile

Set up a profile <how-to/profile-setup>
Authenticate with AEAT <how-to/authenticate-with-aeat>
Maintain census facts <how-to/censo-update>
Which modelos apply to you <how-to/choose-modelo>
Protect data access <how-to/protect-data-access>
```

```{toctree}
:hidden:
:caption: Your calendar

Filing calendar <how-to/filing-calendar>
AEAT notifications <how-to/check-aeat-notifications>
Filing readiness <how-to/filing-readiness>
```

```{toctree}
:hidden:
:caption: Your ledger

Work with transactions <how-to/import-bank-statements>
Classify transactions <how-to/classify-transactions>
Classify with an LLM <how-to/classify-with-llm>
Attach invoices and receipts <how-to/ledger-evidence>
Manage business invoices <how-to/manage-invoices>
Correct mistakes <how-to/correct-ledger-entries>
IVA prorrata deductions <how-to/prorrata>
```

```{toctree}
:hidden:
:caption: Your filings

The filing workflow <how-to/filing-spine>
Modelo 036 (censo) <how-to/modelo-036>
Modelo 100 (Renta) <how-to/modelo-100>
Modelo 130 (IRPF instalment) <how-to/modelo-130>
Modelo 303 (IVA) <how-to/modelo-303>
Modelo 349 (intra-community) <how-to/modelo-349>
Modelo 390 (IVA summary) <how-to/modelo-390>
Calculation inputs <how-to/review-calculation-values>
Google Sheets review <how-to/review-with-google-sheets>
Verify a filing <how-to/verification-reports>
File at AEAT <how-to/file-at-aeat>
Reconcile a filing <how-to/reconcile>
```

```{toctree}
:hidden:
:caption: Help

Troubleshooting <how-to/troubleshooting>
Disclaimer <disclaimer>
```

```{toctree}
:hidden:
:caption: Reference

CLI reference <cli/index>
Cadrumo reference <reference/index>
Glossary <_generated/glossary>
Casilla reference <_generated/casillas/index>
Legal reference <_generated/legal/index>
```

```{toctree}
:hidden:
:caption: How it works

Overview <explanation/index>
```

```{toctree}
:hidden:
:caption: Project

Updates and downloads <updates>
Architecture <architecture/index>
Authoring guide <authoring-guide>
API <api/index>
```
