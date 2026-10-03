<p align="center">
  <img src="docs/_static/readme/cadrumo-logo.svg" alt="Cadrumo logo" width="136">
</p>

# Cadrumo

**Prepare your Spanish taxes. Know where the numbers come from.**

[![Apache 2.0 license](https://img.shields.io/badge/license-Apache%202.0-blue)](LICENSE)
![Status: beta](https://img.shields.io/badge/status-beta-yellow)

Cadrumo is a local-first workbench for preparing Spanish taxes. Bring bank transactions, invoices, and taxpayer records into one place, trace the figures in your return, and export supported filing files.

Connect your bookkeeping to your return through the interactive terminal workbench, CLI, or an AI assistant connected through the Model Context Protocol (MCP).

[Get started](#get-started) · [User guides](#user-documentation) · [Technical documentation](#technical-documentation)

## From records to a return you can review

- **Bring your records together.** Import bank statements and structured invoices, attach supporting documents, and classify income and expenses. Keep each taxpayer's work in a separate profile.
- **Follow the figures back to their sources.** Inspect calculation inputs, formulas, and source references for individual fields in a tax form. Missing inputs remain visible for review.
- **Prepare and check a draft.** Calculate a modelo—a Spanish tax form—for a specific year and period, resolve findings, and export supported filing layouts.
- **Keep track of the work.** Review declarations, deadlines, and outstanding tasks. With authenticated AEAT access, retrieve supported records and reconcile filing receipts with local work.
- **Use assistance where it helps.** Optional AI can propose document extractions and transaction classifications. Tax arithmetic runs through a deterministic calculation engine; agent access is scoped to an authorized profile and operations.

**You submit the return through AEAT.** Cadrumo prepares local files and can retrieve official records, but it does not submit returns. Export availability and portal acceptance depend on the modelo and revision; see the [filing guide](docs/how-to/file-at-aeat.md).

## Get started

Cadrumo is in beta and currently available only through an authorized source checkout. Use the source installation below while public publishing remains blocked. You need **Python 3.13+** and **[uv](https://docs.astral.sh/uv/)**.

From the repository root:

```console
uv sync
uv run aeat --version
uv run aeat --help
```

The package is named `cadrumo`; its command is `aeat`.

Start the terminal workbench:

```console
uv run aeat app tui
```

Create or sign in to a taxpayer profile, then use the workbench to organize your records and review declarations. Storage and profile access may require an unlock prompt. For a guided first return, follow the [quickstart](docs/how-to/quickstart.md).

Prefer commands? Explore the available ledger and declaration operations:

```console
uv run aeat app ledger --help
uv run aeat app modelo --help
```

A typical preparation follows this sequence:

1. **Set up a profile** with the taxpayer's identity, activity, and tax circumstances.
2. **Import and review records** so income, expenses, and supporting evidence are ready.
3. **Calculate and verify a draft** for the chosen modelo and period.
4. **Export and file through AEAT**, then reconcile the official receipt.

Support varies by modelo, year, and available source data. Check the [modelo guide](docs/how-to/choose-modelo.md) before starting a return.

## Your data and your tools

Cadrumo encrypts app-managed financial records and evidence in local profile storage. Original imported files remain at their source paths; filing exports are cleartext files at the destinations you choose.

External connections serve specific tasks: authenticated AEAT reads, optional Google Sheets workbooks, and optional hosted AI processing. Sending evidence to a hosted model requires explicit consent. See [data access](docs/how-to/protect-data-access.md) and the [privacy policy](PRIVACY.md).

The CLI, terminal workbench, and MCP integration use the same local runtime and application operations. An assistant can help with permitted tasks while calculation, access checks, and review remain under Cadrumo's application controls. See [connect an agent](docs/how-to/connect-an-agent.md) for setup and permissions.

## User documentation

| I want to… | Start here |
| --- | --- |
| Prepare my first return | [Quickstart](docs/how-to/quickstart.md) |
| Find a workflow or command | [Task guides](docs/how-to/index.md) · [Command reference](docs/reference/commands-and-configuration.md) |
| Check which modelos apply | [Choose a modelo](docs/how-to/choose-modelo.md) |
| Understand a calculated figure | [From records to figures](docs/explanation/from-records-to-figures.md) |
| Connect to AEAT | [Authentication](docs/how-to/authenticate-with-aeat.md) |
| Resolve a setup or workflow issue | [Troubleshooting](docs/how-to/troubleshooting.md) |

## Technical documentation

For the internals, start with the [technical overview and architecture](technical/README.md). The collection connects subsystem explanations to detailed source-analysis articles, preserving their findings and review limits. It is separate from the user guides.

- [Subsystem topics](technical/README.md#topics) and [detailed articles](technical/articles/README.md)
- [Security and trust boundaries](technical/assessments/security-and-trust-boundaries.md)
- [Implementation assessment](technical/assessments/implementation-assessment.md) and [snapshot scope](technical/reading-guide.md)
- [Contributing guide](CONTRIBUTING.md)
- [Changelog](CHANGELOG.md) and [security policy](SECURITY.md)

Report bugs through [GitHub issues](https://github.com/nevenincs/cadrumo/issues). Follow the security policy for vulnerability reports.

## Status and license

Cadrumo is beta software: commands, schemas, and stored state may change without compatibility support before 1.0. Local verification does not establish AEAT acceptance or guarantee correct tax treatment.

Licensed under [Apache 2.0](LICENSE). Cadrumo is independent of AEAT and does not provide tax, legal, accounting, or financial advice. See the [full disclaimer](docs/disclaimer.md).
