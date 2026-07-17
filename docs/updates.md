# Updates and downloads

Use this page as the project-facing hub for release notes, critical notices,
download links, event notes, and support routes. The banner and footer point here
so important project status is available from every documentation page.

```{important}
`aeat` is pre-alpha software. Treat every release note as potentially relevant
before upgrading, and verify filing deadlines, forms, and submission rules with
official AEAT sources before you file.
```

::::{grid} 1 2 2 2
:gutter: 3
:class-container: aeat-route-grid

:::{grid-item-card} Latest download
:link: https://github.com/wgergely/aeat/releases/latest
:link-type: url
:class-card: aeat-route-card

Start with the latest release when a packaged download is available. Record the
installed version before preparing any filing records.
:::

:::{grid-item-card} Critical updates
:link: https://github.com/wgergely/aeat/releases
:link-type: url
:class-card: aeat-route-card

Use release notes to check breaking changes, migration notes, supported workflows,
and known limitations before changing versions.
:::

:::{grid-item-card} Report an issue
:link: https://github.com/wgergely/aeat/issues
:link-type: url
:class-card: aeat-route-card

Open an issue for defects, confusing documentation, missing workflow coverage, or
release notes that need clarification.
:::

:::{grid-item-card} Source repository
:link: https://github.com/wgergely/aeat
:link-type: url
:class-card: aeat-route-card

Use the repository for source code, development history, project metadata, and
links to release and issue activity.
:::

::::

## Current status

`aeat` is local-first, pre-alpha software for preparing Spanish tax filing
records. It does not submit declarations for you, does not replace official AEAT
tools, and is not affiliated with AEAT.

Expect breaking changes while the CLI workflows, generated documentation, and
modelo coverage are still being hardened. Before relying on a version for a
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

Use the latest release link when you need the current packaged version. If a
packaged artifact is not available for your environment, use the repository and
record the commit or tag you installed from.

After installing or upgrading, run:

```console
$ aeat --version
```

Keep that version with the local export, AEAT submission receipt, and any
reconciliation notes for the filing period.

## Events and deadlines

This documentation may describe filing workflows and preparation order, but it
does not publish an authoritative tax calendar. Always confirm deadlines,
forms, and official changes with AEAT or a qualified professional before filing.

Project events that affect documentation readers should be announced through:

- the site banner for short-lived notices;
- this page for durable update and download routes;
- release notes for version-specific changes;
- issues for open defects, regressions, and documentation gaps.
