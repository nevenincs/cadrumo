# aeat

A Spanish tax-filing assistant, driven by a deterministic engine and an agent harness.

At the core of `aeat` is a comprehensive command line that you and your agent operate together. It's for autónomos, small businesses, and the people who help them file. It ingests your financial records, calculates each modelo's figures, and prepares the filing: checked against the form's rules, grounded in the regulation that defines each casilla, and exported ready to upload. Your responsibility is to verify the result and to file it yourself, through the official channels of the Agencia Estatal de Administración Tributaria (AEAT).

You run it as a Claude plugin, through any Model Context Protocol (MCP) client, or directly at the terminal. Describe your situation in plain language; the assistant drives the toolkit, and the deterministic engine computes every figure and cites the legal rule behind it.

> **Verify everything.** `aeat` works to ground every figure in current regulation and cites its sources, but it can make mistakes. Never accept a result blindly. You remain responsible for every declaration you file, and the authors accept no liability for incorrect output.
>
> **Status: beta.** Expect breaking changes between versions. The web home at `aeat.neve.md` is under construction; until it lands, this repository is the canonical source.

## What you use it for

- Keep an encrypted ledger of transactions, invoices, and supporting evidence
- Classify each entry for IRPF (personal income tax) and IVA (value-added tax), including mixed business and personal use
- Calculate a modelo's figures from the ledger, grounded in the BOE (Boletín Oficial del Estado) and AEAT rules that define each casilla
- Verify a draft against the form's own consistency checks before anything leaves your machine
- Export a submission-ready file in the official format
- Reconcile your records against the justificante AEAT issues after you file

## What it is not

- **It never files.** No submit command exists, and no code path contacts AEAT to file on your behalf. You upload the exported file through AEAT's own tools.
- **It isn't a tax adviser.** It computes and checks figures from published rules; it doesn't judge your situation. When in doubt, consult a professional.
- **It isn't affiliated with AEAT**, and it doesn't replace AEAT's official software.
- **It prepares one taxpayer at a time.** Profiles keep each taxpayer's records separate and encrypted.

## Spanish tax terms

These terms appear throughout the project:

- **Modelo** - an AEAT tax form, named by a three-digit code such as 100 (annual income tax), 130 (quarterly income-tax instalment), or 303 (quarterly IVA).
- **Casilla** - a single numbered field on a modelo.
- **Justificante** - the receipt PDF AEAT issues after you file, carrying the verification code and the filed figures.
- **Autónomo** - a self-employed individual who files their own taxes with AEAT.

## How it works

The project is two halves: an agent harness that the assistant loads to operate safely, and a deterministic engine that does the tax work. The assistant orchestrates, extracts, and narrates; the engine computes. No tax value ever comes from a language model.

### The agent harness

The harness is the operating layer the assistant loads before touching your records:

- **Operator rules** - the always-on contract: read the typed result envelopes, preserve provenance, never guess a figure, stop at the filing boundary.
- **Personas** - seven scoped roles (coordinator, onboarding, ledger groomer, classifier, modelo preparer, verifier, reconciler), each limited to the tools its job needs.
- **Skills** - situation-keyed playbooks selected by who you are (an autónomo in estimación directa, a sociedad, an arrendador), what's happening (a quarter closes, an activity starts), or which modelo is due (such as 130, 303, and 390).
- **The operating console** - one MCP server, `aeat-mcp`, exposes the toolkit to any MCP client. It carries grounded search over the bundled BOE and AEAT legal corpus, a Spanish tax terminology lookup, a capability contract, and gated command execution.

Consequential actions pass a human-in-the-loop gate: reads run freely, local changes ask for confirmation where it matters, and anything that would write to AEAT is refused outright.

### The CLI as the brain

Under the harness sits `aeat`, a Python CLI published on PyPI as [`aeat-cli`](https://pypi.org/project/aeat-cli/). It's a self-contained tax engine and works without any AI in the loop:

- Modelo definitions live in a versioned registry compiled from TOML. Every casilla carries the legal references and official sources that define it, keyed by filing year and revision.
- Every command emits a versioned JSON envelope with a stable exit-code table and typed notices, so an assistant or a script reads outcomes without scraping text.
- Financial data persists only in encrypted storage on your machine, unlocked through your OS keychain or a passphrase fallback.
- The surface is two command families: `aeat config` (profiles, authentication, diagnostics) and `aeat app` (ledger, modelos, registry, read-only live AEAT pulls).

## Install

### The Claude plugin (recommended)

You need [Claude Code](https://claude.com/claude-code) or the Claude desktop app, plus [uv](https://docs.astral.sh/uv/); the plugin launches the published `aeat-cli` package with `uvx`.

```
/plugin marketplace add nevenincs/neve-marketplace
/plugin install aeat@neve
```

One install carries the skills, the personas, and the operating console. Then ask for what you need in plain language: "set up my taxpayer profile", "import this bank statement", or "prepare my Modelo 303 for 3T". The [quickstart](docs/how-to/quickstart.md) walks the full path from an empty profile to an exported file.

### The CLI on its own

If you prefer the terminal, or want the console in a different MCP client:

```bash
uv tool install aeat-cli
aeat --version
```

Every command carries its own `--help`. Any MCP client runs the same console with:

```bash
uvx --from "aeat-cli[agent]" aeat-mcp
```

If you want to inspect or adapt the harness itself, `aeat app agent --output=<dir>` writes it to disk as a Claude-native workspace, and `aeat app agent --output=<dir> --layout=plugin` writes the plugin tree.

## Documentation

The [`docs/`](docs/index.md) tree holds the full documentation:

- [Quickstart](docs/how-to/quickstart.md) - profile, ledger, and a first modelo export.
- [Tutorial](docs/tutorials/index.md) - build a Modelo 130 filing end to end.
- [How-to guides](docs/how-to/index.md) - task recipes for the day-to-day workflow.
- [How it works](docs/explanation/index.md) - how records become modelo figures, and why `aeat` never files.
- [Architecture overview](docs/architecture/index.md) - the layered design, the registry pipeline, and the storage model, for readers who want the whole picture.

Run `just docs` to build the rendered site, which adds the command-line and API reference.

## Safety and privacy

- Building, checking, and exporting happen locally. Live AEAT access is read-only - pulling your justificantes, notifications, and censo data - and each profile opts in to it per capability.
- Ledger rows, invoices, and evidence bytes persist only inside encrypted storage on your machine. There's no cloud backend.
- When an assistant operates the toolkit, your chat provider sees the conversation and the figures discussed in it, nothing more.

## Getting help

Report bugs and ask questions on the [issue tracker](https://github.com/nevenincs/aeat/issues). Report a security vulnerability privately instead, following [`SECURITY.md`](SECURITY.md).

## Contributing

- The local quality gates are the source of truth: `just check-style`, `just check-types`, `just test-unit`, and `just check-pre-commit`.
- Build the docs with `just docs`; check them with `just docs-check`.
- Adding a modelo to the registry starts with `python -m dev.registry.newmodelo scaffold <modelo-id> <revision-id>`, which writes the authoring skeleton and prints the contributor checklist.
- The agent-driven contribution workflow is documented in [`CLAUDE.md`](CLAUDE.md).

## License

Apache 2.0. See [LICENSE](LICENSE).

## Disclaimer

This project is not a substitute for professional tax advice, and it isn't affiliated with AEAT. It never submits filings; you upload any exported file through AEAT's official tools yourself and remain responsible for every declaration. The authors accept no liability for filings produced or actions taken with this software. Read the [full disclaimer](docs/disclaimer.md) before relying on `aeat`.
