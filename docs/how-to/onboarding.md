# Set up a fresh workstation

Use this the first time you install `aeat` on a clean machine. It takes you from
an empty checkout to a working tool, shows you how to check what is missing, and
lets you choose which optional services to turn on.

`aeat` works without any optional service. Google export, on-host LLM vision, and
cloud LLM upload are opt-in. The core filing workflow runs with none of them.

## Install the environment

Install the project and its tools in one step:

```bash
just bootstrap
```

This installs the Python environment, syncs every dependency group, and runs the
readiness check at the end.

## Check what is ready

Ask `aeat` what is installed and what is missing:

```bash
just doctor
```

`just doctor` runs `aeat config check`. The report lists each external
dependency, whether it is available, and the exact command to fix any gap. It
also shows your profile's capability posture. It exits with an error when a
capability you turned on has a missing dependency.

Run the check directly for machine-readable output:

```bash
aeat config check --format json
```

## Install optional integrations

The core install is lean. Google export, the live AEAT browser, and the
Anthropic-API provider are optional package extras. Install only the ones you
need:

```bash
pip install "aeat[google]"
pip install "aeat[browser]"
pip install "aeat[anthropic]"
pip install "aeat[all]"
```

`aeat config check` lists each extra and prints the exact install command for any
that is missing. A feature whose extra is not installed refuses with the same
hint instead of failing obscurely.

## Provision optional dependencies

Install the optional browser and model dependencies when you need them.

Install the Playwright browser used for live AEAT reads:

```bash
just provision
```

Install the on-host vision model used to read invoices. Start the Ollama server
and pull the model named in the report:

```bash
ollama serve
ollama pull qwen2.5vl:7b
```

Install a cloud LLM provider CLI when you want cloud classification. Put its
executable on `PATH` and sign in with that provider's own flow. See
[LLM provider setup](setup-llm-classification.md).

Run `just doctor` again after each change to confirm the gap is closed.

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
you can set them during onboarding. See [Set up a profile](profile-setup.md).

## Next steps

- [Quickstart](quickstart.md)
- [Set up a profile](profile-setup.md)
- [LLM provider setup](setup-llm-classification.md)
- [Troubleshooting](troubleshooting.md)
