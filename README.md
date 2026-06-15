# aeat

`aeat` is a helper for preparing your Spanish tax forms. It takes the records you keep, works out the figures for each modelo, checks them against the form's rules, and exports a file ready to submit to the Agencia Estatal de Administración Tributaria (AEAT).

> **Status: pre-alpha.** Expect breaking changes between versions.

## Spanish tax terms

These terms appear throughout the documentation:

- **Autónomo** is a self-employed individual who files taxes to AEAT.
- **Modelo** is an AEAT tax form. A three-digit code names it, such as 100 (personal income tax), 130 (quarterly income-tax instalment), or 303 (value-added tax).
- **Casilla** is a single numbered field on a modelo.
- **Justificante** is the receipt PDF AEAT issues after you file. It carries the verification code and the filed figures.

## Who it's for

`aeat` is for autónomos and small businesses who file their own taxes, and for the people who help them. It works one taxpayer at a time. It isn't a tax adviser, and it doesn't replace AEAT's official tools.

Use `aeat` to:

- Keep a ledger of your financial records
- Compute the figures for a modelo from those records
- Check a draft against the justificante AEAT issues after a filing
- Export a file that's ready to upload to AEAT

## Safety

`aeat` builds, checks, and exports your filings. It doesn't file them. You upload the exported file to AEAT yourself, through the official channel. No submit command exists, and no code path contacts AEAT to file on your behalf.

## Installation

You need Python and the uv package manager:

- Python 3.13 or newer
- [uv](https://docs.astral.sh/uv/)

Clone the repository, bootstrap it, then confirm the command line responds:

```bash
git clone https://github.com/wgergely/aeat
cd aeat
just bootstrap
aeat --version
```

`just bootstrap` installs the dependencies, provisions `env/.env`, and runs the
workstation check. The version command prints a single line, such as `aeat 0.1.0`.

Check the optional external services (on-host LLM vision via Ollama, the cloud
provider CLIs, the Playwright browser) any time, with the exact fix for each gap:

```bash
just doctor          # or: aeat config check
just provision       # install the Playwright browser binary
```

Each profile opts in or out of these services independently — see
`aeat config profile capabilities show`.

## The command line

`aeat` has two command families:

- **`aeat config`** sets up your configuration: operator profiles, authentication, and diagnostics.
- **`aeat app`** runs the tax workflow over your active profile: your ledger, your modelo drafts, and the tax-form registry.

Every command carries its own `--help`.

## Getting help

Report bugs and ask questions on the [issue tracker](https://github.com/wgergely/aeat/issues).

## Documentation

The full documentation lives under [`docs/`](docs/index.md):

- [Quickstart](docs/how-to/quickstart.md) - the short path from profile and ledger to a modelo file.
- [Set up your taxpayer profile](docs/how-to/profile-setup.md) - create a profile and switch between several.
- [Work with Transactions](docs/how-to/import-bank-statements.md) - import, add, edit, classify, and review ledger rows.
- [Tutorial](docs/tutorials/index.md) - build your first modelo end to end.
- [How-to recipes](docs/how-to/index.md) - set up profiles, link censo facts, work with transactions, file 303 or 390, verify, export, and diagnose problems.
- [Explanation](docs/explanation/index.md) - how the pipeline works and why `aeat` never files.
- [Glossary](docs/glossary.md) - the Spanish tax terms these docs use.

Run `just docs` to build the rendered site, which adds the command-line and source-code reference.

## For contributors

Contributor documentation lives separately from this user guide.

- Build the documentation with `just docs`, and check it with `just docs-check`. The built site holds the command-line and source-code reference.
- The local quality gates are the source of truth: `just check-style`, `just check-types`, `just test-unit`, and `just check-pre-commit`.
- The [architecture overview](docs/architecture.md) explains how the codebase fits together.
- The agent-driven contribution workflow is documented in [`CLAUDE.md`](CLAUDE.md).

## License

Apache 2.0. See [LICENSE](LICENSE).

## Disclaimer

This project is not a substitute for professional tax advice. It isn't affiliated with AEAT. It never submits filings; you upload any exported file through AEAT's official tools yourself. Use it at your own risk, as the authors accept no liability for filings produced or actions taken with this software. If in doubt, consult a qualified tax professional.
