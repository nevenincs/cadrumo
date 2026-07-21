# Updates and downloads

Use this page as the project-facing hub for release notes, critical notices,
download links, event notes, and support routes. The banner and footer point here
so important project status is available from every documentation page.

```{important}
Cadrumo is in beta. Treat every release note as potentially relevant
before upgrading, and verify filing deadlines, forms, and submission rules with
the Agencia Estatal de Administración Tributaria (AEAT) before you file.
```

::::{grid} 1 2 2 2
:gutter: 3
:class-container: cadrumo-route-grid

:::{grid-item-card} Latest download
:link: https://github.com/nevenincs/cadrumo/releases/latest
:link-type: url
:class-card: cadrumo-route-card

Start with the latest release when a packaged download is available. Record the
installed version before preparing any filing records.
:::

:::{grid-item-card} Critical updates
:link: https://github.com/nevenincs/cadrumo/releases
:link-type: url
:class-card: cadrumo-route-card

Use release notes to check breaking changes, migration notes, supported workflows,
and known limitations before changing versions.
:::

:::{grid-item-card} Report an issue
:link: https://github.com/nevenincs/cadrumo/issues
:link-type: url
:class-card: cadrumo-route-card

Open an issue for defects, confusing documentation, missing workflow coverage, or
release notes that need clarification.
:::

:::{grid-item-card} Source repository
:link: https://github.com/nevenincs/cadrumo
:link-type: url
:class-card: cadrumo-route-card

Use the repository for source code, development history, project metadata, and
links to release and issue activity.
:::

::::

## Current status

Cadrumo is local-first beta software for preparing Spanish tax filing
records ([read the full disclaimer](disclaimer.md)).

Expect breaking changes while the command-line interface (CLI) workflows,
generated documentation, and modelo coverage are still being hardened. Before relying on a version for a
filing period, read the release notes and keep a record of the installed version
used to prepare the export.

## Critical updates

Critical updates are published through the release notes and highlighted through
the site banner when the documentation needs to draw attention to a change.

Check this section when you need to know whether a release affects:

- filing workflow order;
- taxpayer profile setup;
- ledger import or classification behavior;
- modelo calculation, verification, or export behavior;
- storage, receipts, or reconciliation steps.

## Download guidance

Use the latest release link when you need the current packaged version, and
follow the [installation guide](workstation-setup.md) to install it. If no
packaged artifact is available for your environment, open an issue so the gap
is recorded.

After installing or upgrading, run:

```console
$ aeat --version
```

Keep that version with the local export, AEAT submission receipt, and any
reconciliation notes for the filing period.

## Deadlines and project announcements

This documentation may describe filing workflows and preparation order, but it
does not publish an authoritative tax calendar. Always confirm deadlines,
forms, and official changes with AEAT or a qualified professional before filing.

Project events that affect documentation readers should be announced through:

- the site banner for short-lived notices;
- this page for durable update and download routes;
- release notes for version-specific changes;
- issues for open defects, regressions, and documentation gaps.
