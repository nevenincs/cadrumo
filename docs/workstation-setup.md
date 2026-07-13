# Install Cadrumo

This page covers the first-time installation of Cadrumo on your computer: get
the package, confirm the `aeat` command works, and turn on the optional
services you want.

Cadrumo works without any optional service. Google export, on-host LLM vision,
and cloud LLM upload are opt-in. The core filing workflow runs with none of
them.

## Before you start

You need:

- Python 3.13 or newer, with `pip` available.
- Around 200 MB of free disk space.

## Get the package

Download the current Cadrumo package from the
[releases page](https://github.com/nevenincs/cadrumo/releases/latest). Each
release lists its downloadable files and release notes; record the version you
install, as [Updates and downloads](updates.md) recommends.

Install the downloaded wheel file:

```bash
pip install ./cadrumo-0.2.0-py3-none-any.whl
```

Confirm the command is on your path:

```bash
aeat --version
```

## Check what is ready

Ask `aeat` what is installed and what is missing:

```bash
aeat config check
```

The report lists each external dependency, whether it is available, and the
exact command to fix any gap. It also shows your profile's capability posture.
It exits with an error when a capability you turned on has a missing
dependency.

Run the check for machine-readable output when you script the setup.
`--format json` is a global flag, so it goes before the command:

```bash
aeat --format json config check
```

## Install optional integrations

The core install is lean. Google export, the live AEAT browser, the
Anthropic-API provider, and OFX/QFX bank-statement import are optional package
extras. Name the extras you need when you install the wheel:

```bash
pip install "./cadrumo-0.2.0-py3-none-any.whl[google,browser]"
```

The available extras are `google`, `browser`, `anthropic`, `ofx`, `agent`, and
`all`. `aeat config check` lists each extra and prints the exact install
command for any that is missing. A feature whose extra is not installed
refuses with the same hint instead of failing obscurely.

## Provision optional dependencies

Install the optional browser and model dependencies when you need them.

Install the browser used for live AEAT reads. The `browser` extra provides the
`playwright` command:

```bash
playwright install chromium
```

Install the on-host vision model used to read invoices. Start the Ollama
server and pull the model named in the report:

```bash
ollama serve
ollama pull qwen2.5vl:3b
```

Install a cloud LLM provider CLI when you want cloud classification. Put its
executable on `PATH` and sign in with that provider's own flow. See
[Classify transactions with an LLM](how-to/classify-with-llm.md#set-up-a-provider).

Run `aeat config check` again after each change to confirm the gap is closed.

## Choose your service capabilities

Each profile carries its own opt-in for three optional services. Show the
resolved posture:

```bash
aeat config profile capabilities show
```

The three capabilities are:

- `cloud_evidence_upload` — allow sending sensitive evidence to a cloud LLM
  provider. Off by default. Barred for gestor profiles.
- `llm_vision` — read invoices with the on-host vision model. On by default.
- `google_export` — export calculations to Google Sheets. On by default.

Turn a capability on or off for the active profile:

```bash
aeat config profile capabilities set llm_vision off
aeat config profile capabilities set cloud_evidence_upload on
```

The setup wizard also asks these questions when you create or edit a profile, so
you can set them during onboarding. See [Set up a profile](how-to/profile-setup.md).

## Next steps

- [Quickstart](how-to/quickstart.md)
- [Set up a profile](how-to/profile-setup.md)
- [Classify transactions with an LLM](how-to/classify-with-llm.md#set-up-a-provider)
- [Troubleshooting](how-to/troubleshooting.md)
