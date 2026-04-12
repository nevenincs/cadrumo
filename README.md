# aeat

> **Status: pre-alpha.** Local gates are authoritative — `just lint &&
> just typecheck && just test && just hooks` is the source of truth.
> GitHub Actions is permanently disabled on this repository; there is
> no CI badge by design.

Spanish tax authority (AEAT) automation for autónomos: fetch live
filing status, build typed filing drafts, dry-run and submit, all from
the CLI.

## What it does

- **Authenticates against AEAT** with a real PKCS#12 client certificate
  (FNMT-RCM and other accepted CAs) — no Cl@ve / DNIe yet.
- **Reads your filing status** directly from *Mis expedientes* and
  *Mis notificaciones* via a controlled headless browser session.
- **Builds typed filing drafts** for the supported modelos by joining
  the AEAT casilla catalogue, the manual práctico, and the live
  normative corpus.
- **Submits filings dry-run by default**, with the real submission
  gated behind an explicit confirmation. The dry-run-by-default rule
  is a feature, not a bug.
- **Self-heals local state** by reconciling AEAT's view with the
  on-disk store after every sync, so the next run always starts from
  ground truth.

## What it does not do

- It is **not a tax adviser** and **not a substitute** for AEAT's
  official tools or for professional tax advice.
- It will **never submit a filing without explicit confirmation** —
  dry-run is the default, real submission is opt-in per invocation.
- It does **not yet** support Cl@ve, DNIe, or any non-certificate
  authentication path.
- It is **not multi-tenant** — one workstation, one autónomo, one
  certificate at a time.
- It does **not** automate around captchas or other anti-bot defences;
  it pauses and alerts the operator instead.

## Quick start

```sh
git clone https://github.com/wgergely/aeat
cd aeat
just bootstrap            # uv sync, vaultspec install, env/.env, gsuite bootstrap
aeat setup                # interactive setup wizard           (merging in #61)
aeat workflow next        # next dry-run filing in the queue
```

`aeat workflow next` is on `main`. `aeat setup` lands with #61; until
it merges, configure the project by editing `env/.env` directly —
every field is documented inline in `env/.env.example`. Every layer
the workflow composes (cert auth, browser, status reader, filing
draft engine, submission engine, deadline engine, sync, storage) is
already on `main` and exercised by the live test suite. Live tests
are gated behind `AEAT_LIVE_TESTS_ENABLED=1`.

## Architecture

The on-main subpackages under `src/aeat/`:

| Subpackage             | Responsibility                                                            |
| :--------------------- | :------------------------------------------------------------------------ |
| `aeat.models`          | Closed catalogue of supported modelos (130, 303, 390).                    |
| `aeat.portals`         | URL + form metadata for every AEAT portal the project touches.            |
| `aeat.auth`            | PKCS#12 client-certificate authentication and credential resolution.      |
| `aeat.browser`         | Controlled headless Playwright session against AEAT.                      |
| `aeat.schema`          | Pydantic models for every wire and storage record.                        |
| `aeat.normatives`      | Live normative corpus (BOE references, vigencia windows).                 |
| `aeat.manuals`         | Manual práctico ingestion and structured extraction.                      |
| `aeat.deadlines`       | Deadline engine — what's due, when, with what tolerance.                  |
| `aeat.filing`          | Filing draft engine — assembles a typed draft from manuals + casillas.    |
| `aeat.submission`      | Submission engine — dry-run by default, explicit confirm to send.         |
| `aeat.status`          | *Mis expedientes* reader — the authoritative AEAT-side state.             |
| `aeat.inbox`           | *Mis notificaciones* reader — pending notifications and acknowledgements. |
| `aeat.sync`            | Self-healing reconciliation between AEAT-side state and local storage.    |
| `aeat.storage`         | Local on-disk store for filings, receipts, and audit trail.               |
| `aeat.i18n`            | Trilingual (es / en / hu) message catalogue with nested-dict shape.       |
| `aeat.llm`             | Bounded LLM client for manual práctico extraction and explanations.      |
| `aeat.testing`         | Shared fixtures and synthetic filing factories for the test suite.        |
| `aeat.cli`             | Typer-based CLI surface (`aeat ...`).                                     |
| `aeat.workflow`        | Orchestration engine that drives a filing through the pipeline.           |
| `aeat.setup`           | Interactive first-run setup wizard. *(merging in #61)*                    |

A data-flow diagram with one paragraph per arrow lives in
[`docs/architecture.md`](docs/architecture.md). The contributor
walkthrough lives in [`docs/getting-started.md`](docs/getting-started.md).

## Roadmap

Milestones:

- `0.0.1-scaffolding` — repo, tooling, base module structure, dev loop.
- `0.0.2-foundations` — auth, browser, schema, storage, i18n, models.
- `0.1.0-pre-alpha` — **current** — full AEAT loop demoable end-to-end.
- `0.2.0-alpha` — first external contributors, expanded modelo coverage.
- `0.3.0-beta` — packaging, distribution, documentation site.
- `1.0.0` — production-ready for a single autónomo.

## Contributing

- **Conventional commits are mandatory** on every commit on every
  branch. Format: `<type>(<scope>): <subject>`. Valid types: `feat`,
  `fix`, `perf`, `revert`, `docs`, `refactor`, `chore`, `test`,
  `build`, `ci`, `style`. The type drives the CHANGELOG section when
  `just release` runs — see [`RELEASING.md`](RELEASING.md).
- **One branch per issue.** Branch naming is `<type>/<issue>-<subject>`
  where type ∈ {`feature`, `bug`, `chore`}. Each branch lives in its
  own git worktree.
- **Vault-driven pipeline.** Significant work flows through the
  vaultspec pipeline: research → ADR → plan → execute → code review.
  Artefacts live under `.vault/`.
- **Local gates are authoritative.** GitHub Actions is permanently
  disabled on this repository. Before every commit and before every
  PR:

  ```sh
  just lint           # ruff
  just typecheck      # ty
  just test           # pytest, default skip-live
  just hooks          # prek run --all-files
  ```

aeat oauth-client init [--json PATH]    # walk through Cloud Console OAuth Desktop client setup
```

`uv run aeat --help` (and `--help` on any sub-command) prints the
authoritative version.

## Casillas corpus

The curated casilla workflow is exposed through `aeat casillas ...`.
Contributor guidance for adding a new `(modelo, period)` catalogue lives in
`docs/casillas.md`.

## Doctor

`aeat doctor` is the single source of truth for "is my workstation
actually set up". It produces a rich table covering:

- `env/.env` file presence and `GOOGLE_CLOUD_PROJECT` non-empty
- gcloud binary on PATH, version, active account, project match
- Application Default Credentials JSON file present + scopes superset
  of the Drive/Sheets/Docs/cloud-platform/userinfo.email set
- Each of the eight required APIs enabled in the project (via Service
  Usage)
- Live round-trip calls: `drive.about().get`, `spreadsheets.get` against
  the scratch sheet, `documents.get` against the scratch doc, Cloud
  Functions / Run / Storage `list` calls
- Advisory rows for the optional service-account and OAuth Desktop
  client paths, and the live-tests opt-in flag

The command exits non-zero on any required `MISSING` / `WARN` row, so
it is CI-usable as a gating step.

## Authentication strategy

The CLI supports three credential paths and resolves them in priority
order via `aeat.auth.get_credentials()`:

| Path                    | When to use                                | Provisioned by                        |
| ----------------------- | ------------------------------------------ | ------------------------------------- |
| Application Default Credentials (ADC)  | local development (default) | `just gcloud-auth`                    |
| OAuth 2.0 Desktop client               | user-delegated scopes ADC cannot grant | `just gsuite-oauth-client`            |
| Service account JSON key               | server-side / CI / Cloud Functions         | manual via Cloud Console + IAM        |

### ADC (the default dev path)

Set up by `just gcloud-auth`. One browser flow grants every Workspace
scope the CLI needs. Lives at the documented well-known location
(`%APPDATA%\gcloud\application_default_credentials.json` on Windows,
`~/.config/gcloud/application_default_credentials.json` on Unix). Token
refresh is handled by `google-auth` automatically.

### OAuth 2.0 Desktop client (optional)

Needed only when ADC cannot grant the scope you need (e.g. some
Workspace admin scopes, Gmail send-as). Run:

```sh
just gsuite-oauth-client
```

The helper prints the deep-link to the Cloud Console credentials page
for your active project, lists the exact required fields, and (when you
re-run it with `--json <path>`) parses the downloaded JSON and writes
`GOOGLE_OAUTH_CLIENT_ID` / `GOOGLE_OAUTH_CLIENT_SECRET` into `env/.env`.

### Service account (server / CI)

Create the service account, download a JSON key, and set
`GOOGLE_APPLICATION_CREDENTIALS` in `env/.env` to its path:

```sh
gcloud iam service-accounts create aeat-automation \
    --display-name="AEAT Automation"

gcloud projects add-iam-policy-binding ${GOOGLE_CLOUD_PROJECT} \
    --member="serviceAccount:aeat-automation@${GOOGLE_CLOUD_PROJECT}.iam.gserviceaccount.com" \
    --role="roles/drive.file"

gcloud iam service-accounts keys create credentials/service-account.json \
    --iam-account=aeat-automation@${GOOGLE_CLOUD_PROJECT}.iam.gserviceaccount.com
```

> **Domain-wide delegation:** to access Workspace files owned by other
> users, enable DWD in the Admin console and set
> `GOOGLE_IMPERSONATE_EMAIL` to the target user's email. DWD requires a
> Workspace tenant — it does not work on consumer Gmail.

## Consumer Gmail vs Workspace tenancy

The bootstrap pipeline is designed to work on both consumer Google
accounts (`@gmail.com`) and Google Workspace tenants, but consumer
accounts have one hard limitation worth knowing up front:

**Service accounts on consumer Gmail have zero Drive storage quota.**

That means `just gsuite-bootstrap-sa` (the autonomous service-account
path) succeeds for IAM, Service Usage, Cloud Storage / Functions /
Run, but Drive/Sheets/Docs operations under the SA return
`storageQuotaExceeded`. The bootstrap exits with a clear message
pointing at the workaround. To use Drive/Sheets/Docs on a consumer
Gmail account you must instead run the OAuth Desktop client path:

```sh
just gsuite-oauth-client          # prints Console URL + required fields
# (operator clicks through, downloads JSON to ~/Downloads/client.json)
uv run aeat oauth-client init --json ~/Downloads/client.json
just gcloud-auth                  # uses --client-id-file=env/oauth-client.json
just gsuite-enable-apis
uv run aeat bootstrap
uv run aeat doctor
```

This is a Google product limitation, not a code issue. Workspace
tenants get Shared Drives and domain-wide delegation, both of which
sidestep the SA quota; consumer accounts get neither.

Cloud Functions / Cloud Run / Cloud Storage additionally need an
active billing account on the project. The
`just gsuite-enable-apis-billing` recipe enables those three APIs once
billing is linked. Doctor reports them as advisory rows; live tests
for the cloud surfaces skip cleanly when billing is not enabled.

## Live smoke tests

Live tests hit real Google APIs against the scratch resources
provisioned by `aeat bootstrap`. They are gated behind two
preconditions:

1. `AEAT_LIVE_TESTS_ENABLED=true` in `env/.env`.
2. The relevant `AEAT_SCRATCH_*_ID` set (also written automatically
   by `aeat bootstrap`).

Tests with unmet preconditions skip cleanly with a clear message —
they never silently pass.

```sh
# default: skip live tests
just test

# opt in: hit real Google APIs
just test-live
```

The live suite covers Drive create/list/download/delete, Sheets
set/get/append/clear, Docs append/get/replace, and Cloud Storage /
Functions / Run list calls. Each test cleans up everything it creates
in a `try/finally` and uses a UUID prefix so two parallel runs cannot
collide.

## Development

```sh
just lint           # ruff
just fmt            # ruff format
just typecheck      # ty
just test           # pytest, default skip-live
just test-live      # pytest -m live
just hooks          # prek run --all-files
```

The full just recipe list is `just --list`.

Live tests are opt-in via `AEAT_LIVE_TESTS_ENABLED=1` and hit real
AEAT / Google endpoints; never enable them on shared infrastructure.

The full rules for the agent-driven workflow live in
[`CLAUDE.md`](CLAUDE.md).

## License

Apache 2.0 — see [LICENSE](LICENSE).

## Disclaimer

Tax automation is legally significant. **This project is not a
substitute for professional tax advice and is not affiliated with the
Agencia Estatal de Administración Tributaria (AEAT).** Every
submission path is dry-run by default; the real submission requires an
explicit, per-invocation confirmation by the operator. Use at your own
risk. The authors accept no liability for filings produced or actions
taken with this software. If in doubt, consult a qualified tax
professional and use AEAT's official tools.
