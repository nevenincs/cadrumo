# aeat

`aeat` is a local-first Python toolkit that builds, validates, verifies, and exports Spanish tax filings for autónomos and small businesses. It models tax records, computes modelo figures from your financial input, reconciles drafts against official justificantes, and produces export files you then file yourself. It never submits anything to the Agencia Estatal de Administración Tributaria (AEAT) on your behalf.

> **Status: pre-alpha.** Local gates are the source of truth: `just lint`, `just typecheck`, `just test`, and `just hooks`.

## Who it's for

`aeat` helps autónomos, small businesses, and the people who support them prepare AEAT filings on their own machine. Use it to:

- model tax records and keep a per-operator ledger of financial input,
- compute the figures for a modelo from that input, using registry-grounded formulas,
- reconcile a draft against the official justificante AEAT issues after a filing,
- produce an export file ready for manual upload through the AEAT website.

`aeat` works one operator at a time. It is not a tax adviser, and it does not replace AEAT's official tools or professional tax advice.

## Safety posture - read this first

`aeat` builds, validates, verifies, and exports. It does not file. You upload the exported file to AEAT yourself, through the official channel.

This boundary is structural, not a setting you flip. The toolkit has no submit command and no outbound submission adapter. Read-only live checks against external services stay off by default. To run them once, set the `AEAT_LIVE_TESTS_ENABLED` environment variable to `1`. Everything else runs locally against your own data.

## Installation

You need:

- Python 3.13 or newer,
- the [uv](https://docs.astral.sh/uv/) package manager.

Install the dependencies and confirm the CLI responds:

```bash
uv sync
aeat --version
```

The version command prints a single line, such as `aeat 0.1.0`.

## The command line at a glance

`aeat` exposes two root command families:

- **`aeat config`** manages durable configuration: operator profiles, authentication, and repair or diagnostics.
- **`aeat app`** runs the tax workflow over your active profile: the ledger, modelo work units, the registry, and review.

Start by listing what's available, then create your first profile:

```bash
aeat --help
aeat config profile create
```

Every command and subcommand carries its own `--help`.

## Your first filing

The [getting started guide](docs/getting-started.md) walks you from a fresh install to a validated, exported modelo draft - a file ready for you to upload to AEAT.

## Glossary

- **Autónomo** - a self-employed individual who files taxes to AEAT.
- **Modelo** - a three-digit AEAT tax-form code, such as 100 (personal income tax), 130 (quarterly income-tax instalment), or 303 (VAT).
- **Casilla** - a single field on a modelo, identified by its number (and, on multi-segment modelos, a record-segment code).
- **Justificante** - the receipt PDF AEAT issues after a successful filing, carrying the verification code and the filed figures.

## Getting help and reporting issues

Report bugs and ask questions on the [issue tracker](https://github.com/wgergely/aeat/issues).

## Where to go next

- [Getting started](docs/getting-started.md) - install, configure a profile, and build your first draft.
- [Architecture](docs/architecture.md) - the layering, the registry authority flow, and the documentation surfaces.
- CLI reference - generated from the command tree; build the docs to read it.
- API reference - generated from the source docstrings; build the docs to read it.

Contributors build and check the documentation with the project's `uv` and `just` workflow:

```bash
just docs
just docs-check
```

The agent-driven contribution workflow is documented in [`CLAUDE.md`](CLAUDE.md).

## License

Apache 2.0 - see [LICENSE](LICENSE).

## Disclaimer

Tax automation is legally significant. This project is not a substitute for professional tax advice and is not affiliated with the Agencia Estatal de Administración Tributaria (AEAT). This codebase permanently forbids live submission to AEAT. You upload any exported filing through AEAT's official tools yourself. Use it at your own risk. The authors accept no liability for filings produced or actions taken with this software. If in doubt, consult a qualified tax professional and use AEAT's official tools.
