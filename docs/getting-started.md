# Getting started

This walkthrough takes a brand-new self-employed operator (*autónomo*)
from a fresh workstation to a first read-only filing package. It
assumes you can read English but does not assume any Python
experience. Every command can be copy-pasted verbatim.

## Acronyms used in this guide

- **AEAT** — *Agencia Estatal de Administración Tributaria*, the
  Spanish tax authority.
- **NIF / NIE / CIF** — *Número de Identificación Fiscal* (and its
  variants for foreign residents and legal entities), the
  national-tax-ID format every filing surfaces.
- **IRPF** — *Impuesto sobre la Renta de las Personas Físicas*,
  Spanish personal income tax.
- **IVA** — *Impuesto sobre el Valor Añadido*, Spanish VAT.
- **BOE** — *Boletín Oficial del Estado*, the official state gazette
  carrying every legal citation the project links to.
- **CCAA** — *Comunidad Autónoma*, an autonomous community of Spain.
- **PKCS#12** — public-key cryptographic standard #12, the wrapper
  format used by the FNMT-RCM client certificate (`.p12` / `.pfx`).
- **Sede Electrónica** — AEAT's online filing portal at
  ``sede.agenciatributaria.gob.es``.

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

## Authentication today

The current operator-facing login path is certificate-only. You need
a working FNMT-compatible certificate setup for live AEAT access.

Internally, the auth layer hangs off a provider-generic seam so
future login providers can plug into the same workflow. Those future
providers are not shipped as usable CLI login options today.

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
aeat setup
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

If you prefer editing `env/.env` by hand instead of running the
wizard, every field is documented inline in `env/.env.example`.

### 3a. Security layer

`aeat setup` triggers master-key minting as a side effect of writing
the operator profile (which itself is encrypted at rest). On a
brand-new installation the substrate logs a recovery-key nudge after
the silent mint pointing you at the explicit provisioning command:

```sh
aeat security provision
```

This prompts you for a backend (`keyring` recommended, `file` for
headless / CI), mints the master key, and **displays a 24-word
recovery key once**. Print it. Store it somewhere safe. Without
the recovery key, a forgotten passphrase or lost keychain means
losing every persisted record.

To restore a lost passphrase later:

```sh
aeat security recover --recovery-key "<your 24 words>"
```

To export a portable backup of the master-key state for off-site
storage:

```sh
aeat security key-export --out backup/master-key.json
```

The full operator runbook for these commands lives alongside the
project's other contributor docs.

For testing / throwaway environments the substrate also offers an
`unsecured` backend (published deterministic master key, zero
confidentiality). It refuses real NIFs at profile-write time and
requires the explicit `AEAT_ALLOW_UNENCRYPTED=1` env var.

## 4. Verify

```sh
aeat doctor              # full read-only health check
aeat setup verify --from path/to/setup-answers.json
```

`aeat doctor` walks every dependency the CLI needs (binaries on
`PATH`, env-file presence, mandatory env vars set, certificate file
readable, storage root writable) and prints a single pass/fail table.
It exits non-zero on any required failure, so it is safe to drop into
a pre-flight script.

`aeat setup verify` is a local verifier for a `SetupAnswers` JSON
file. It checks whether the recorded certificate/tooling setup is
internally consistent; it does not open a real AEAT session.

## 5. First run

```sh
aeat workflow next
```

`aeat workflow next` looks at the deadline engine, picks the next
filing that is due (or due soon, within the configured tolerance),
builds a typed draft against the manual práctico and the casilla
catalogue, runs read-only preflight, and prints the draft diagnostics
and diff against the last successful filing for the same modelo.

**Nothing is sent to AEAT.** The CLI has no live-submit path. The
operator's normal command-line flow remains produce → verify →
export, followed by a manual upload through AEAT's own portal.

If the engine encounters a captcha, an unexpected modal, or any AEAT
response it does not recognise, it pauses, takes a screenshot into
the storage root, and alerts you. It will never click through an
anti-bot defence on its own.

## 6. Common questions

**Where does the certificate go?** Anywhere you like — point the
relevant env var (set by `aeat setup`) at the absolute path. The
project does not move or copy your certificate.

**How do I rotate the certificate?** Replace the `.p12` file at the
configured path and re-run the relevant local verification checks.
There is no per-tenant state tied to the certificate fingerprint.

**The workflow says "deadline passed" — now what?** AEAT charges
late-filing surcharges. The project flags the draft as overdue; you
should consult AEAT's official late-filing flow before manually
uploading anything.

**What if AEAT serves a captcha?** The project pauses and alerts.
**Never automate around it.** Solve the captcha in a real browser,
re-run `aeat workflow next`, and the engine picks up where it stopped.

**How do I run the live-read test suite?** Set
`AEAT_LIVE_TESTS_ENABLED=1` in your shell (or in `env/.env`), then
`just test-live`. Live-read tests hit real AEAT endpoints with your
real auth provider; write-shaped live tests are permanently banned.

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
