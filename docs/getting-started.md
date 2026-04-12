# Getting started

This walkthrough takes a brand-new autónomo from a fresh workstation
to a first dry-run filing. It assumes you can read English but does
not assume any Python experience. Every command can be copy-pasted
verbatim.

## 1. Prerequisites

You will need:

- **Python 3.13** on `PATH`. Check with `python --version`.
- **[uv](https://docs.astral.sh/uv/)** — the project's package
  manager. Install via `pipx install uv` or follow the upstream
  instructions.
- **[just](https://github.com/casey/just)** — the project's task
  runner. `cargo install just`, `brew install just`, or
  `winget install Casey.Just`.
- **[gh](https://cli.github.com/)** — only required if you want to
  cut a release later; `git` alone is enough for day-to-day work.
- **A digital certificate (`.p12` / `.pfx`)** issued by FNMT-RCM or
  another AEAT-accepted certification authority, plus its passphrase.
  This is the same certificate you would import into your browser to
  log into AEAT manually.

> The project never reads your certificate's passphrase from a config
> file or a flag. The passphrase is supplied via an environment
> variable whose name is documented during `aeat setup`; the actual
> value is never logged or echoed.

## 2. Install

Clone the repository and run the bootstrap recipe:

```sh
git clone https://github.com/wgergely/aeat
cd aeat
just bootstrap
```

`just bootstrap` performs, in order:

1. `uv sync` — installs runtime and dev dependencies into `.venv/`.
2. `uv run vaultspec-core install --upgrade` — (re-)seeds the
   vaultspec framework files under `.vault/`.
3. `just env-setup` — copies `env/.env.example` to `env/.env` if the
   latter is missing. Edit `env/.env` afterwards to point at your
   certificate, your local storage directory, and the AEAT
   environment (production vs. pre-production).
4. `just gsuite-bootstrap` — provisions the optional Google Workspace
   scratch resources used by the audit-trail integration. You can skip
   this on a pure local install; the rest of the CLI does not depend
   on it.

## 3. Configure

```sh
aeat setup            # merging in #61
```

The setup wizard is a guided pass through the same fields you would
otherwise edit by hand in `env/.env`. It asks for:

- The path to your `.p12` / `.pfx` certificate file.
- The name of the environment variable that will hold its passphrase
  (the wizard never asks for the passphrase itself; you set the env
  var in your shell or in `env/.env`).
- Your NIF and the AEAT environment to target (production or
  pre-production).
- The local storage root for filings, receipts, and the audit trail.
- Which modelos you want enabled (today: 130, 303, 390).

At the end the wizard writes the resolved values to `env/.env` and
prints a summary. Re-run `aeat setup` at any time to reconfigure;
existing values are pre-filled.

Until #61 merges you can configure the project by editing `env/.env`
directly — every field is documented inline in `env/.env.example`.

## 4. Verify

```sh
aeat doctor              # full read-only health check
aeat setup verify        # certificate + AEAT round-trip          (merging in #61)
```

`aeat doctor` walks every dependency the CLI needs (binaries on
`PATH`, env-file presence, mandatory env vars set, certificate file
readable, storage root writable) and prints a single pass/fail table.
It exits non-zero on any required failure, so it is safe to drop into
a pre-flight script.

`aeat setup verify` additionally opens a real AEAT session with your
certificate and reads back your taxpayer profile to confirm the
end-to-end credential chain works. It does not submit anything.

## 5. First run

```sh
aeat workflow next
```

`aeat workflow next` looks at the deadline engine, picks the next
filing that is due (or due soon, within the configured tolerance),
builds a typed draft against the manual práctico and the casilla
catalogue, and prints the dry-run submission payload along with the
diff against the last successful filing for the same modelo.

**Nothing is sent to AEAT.** The default mode is dry-run. To actually
submit, you re-run with the explicit confirm flag the dry-run output
prints — the project never escalates from dry-run to submit
automatically.

If the engine encounters a captcha, an unexpected modal, or any AEAT
response it does not recognise, it pauses, takes a screenshot into
the storage root, and alerts you. It will never click through an
anti-bot defence on its own.

## 6. Common questions

**Where does the certificate go?** Anywhere you like — point the
relevant env var (set by `aeat setup`) at the absolute path. The
project does not move or copy your certificate.

**How do I rotate the certificate?** Replace the `.p12` file at the
configured path and re-run `aeat setup verify`. There is no per-tenant
state tied to the certificate fingerprint.

**The dry-run says "deadline passed" — now what?** AEAT charges
late-filing surcharges. The project will still build the draft but
flags it as overdue; submission proceeds, but you should consult
AEAT's official late-filing flow first.

**What if AEAT serves a captcha?** The project pauses and alerts.
**Never automate around it.** Solve the captcha in a real browser,
re-run `aeat workflow next`, and the engine picks up where it stopped.

**How do I run the live test suite?** Set `AEAT_LIVE_TESTS_ENABLED=1`
in your shell (or in `env/.env`), then `just test-live`. Live tests
hit real AEAT endpoints with your real certificate and can leave
side-effects in pre-production; never enable them in CI or on shared
infrastructure.

## 7. Next steps

- **Supported modelos today:** 130 (pago fraccionado IRPF), 303 (IVA
  trimestral), and 390 (resumen anual IVA).
- **Read the architecture diagram** at
  [`architecture.md`](architecture.md) to understand how a filing
  flows through the system.
- **Read the contributor docs** in [`../README.md`](../README.md) for
  the conventional-commits mandate, the worktree workflow, and the
  vaultspec pipeline.
- **Read the release flow** in [`../RELEASING.md`](../RELEASING.md) if
  you plan to cut a tagged release locally.
