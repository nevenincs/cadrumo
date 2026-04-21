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
just env-setup            # writes env/.env from env/.env.example
# edit env/.env and set GOOGLE_CLOUD_PROJECT
uv run aeat auth init --path desktop-oauth-local-dev
uv run aeat auth init --path desktop-oauth-local-dev --json <downloaded-json>
just bootstrap            # wrapper: deps + gcloud auth + API enablement + aeat bootstrap + aeat doctor
aeat workflow next        # next dry-run filing in the queue
```

Google auth is required because the repo provisions scratch
Drive/Sheets/Docs resources, fetches operator assets from Drive, and
can launch the Google Workspace MCP server. `just bootstrap` is a
wrapper around the local Desktop OAuth path; it does not create the
OAuth Desktop client for you or skip the manual Cloud Console step.
Every field is documented inline in `env/.env.example`. Every layer the
workflow composes (cert auth, browser, status reader, filing draft
engine, submission engine, deadline engine, sync, storage) is already
on `main` and exercised by the live test suite. Live tests are gated
behind `AEAT_LIVE_TESTS_ENABLED=1`.

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

  Common Google auth helpers:

  ```sh
  uv run aeat auth init --path desktop-oauth-local-dev
  uv run aeat auth init --path desktop-oauth-local-dev --json <path>
  uv run aeat doctor                      # verifies Desktop OAuth CLI/bootstrap readiness
  just gcloud-auth                        # optional ADC compatibility step for legacy wrappers
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

`aeat doctor` is a CLI/bootstrap readiness check. It does not, by
itself, prove the Google Workspace MCP launch contract; MCP readiness
additionally requires either Desktop OAuth values in `env/.env` or a
valid `GOOGLE_APPLICATION_CREDENTIALS` path.

## Google auth

Treat Google auth in this repo as exactly two supported operator-facing
paths:

| Path | Default | Use when | What it unlocks |
| ---- | ------- | -------- | --------------- |
| Desktop OAuth local-dev | yes | normal workstation development and any consumer Gmail setup | sets `GOOGLE_AUTH_PATH`, writes Desktop OAuth values, prepares the repo-local CLI/MCP path, then optionally lets `just gcloud-auth` acquire ADC for wrapper compatibility |
| Service-account automation | no | CI, cron, Cloud Functions, or other headless automation | headless Google API access via `GOOGLE_APPLICATION_CREDENTIALS`, optionally with Workspace impersonation |

### Desktop OAuth local-dev (default)

This is the local default. The flow is deliberately two-step:

- `uv run aeat auth init --path desktop-oauth-local-dev` is the guided
  entrypoint. It prints the Cloud Console URL, explains why the step
  exists, and tells Kent what to do next. The legacy
  `just gsuite-oauth-client` recipe is only a wrapper around this
  command.
- After you download the JSON, run
  `uv run aeat auth init --path desktop-oauth-local-dev --json <path>`.
  That copies the JSON to `env/oauth-client.json`, writes
  `GOOGLE_AUTH_PATH`, `GOOGLE_OAUTH_CLIENT_ID`,
  `GOOGLE_OAUTH_CLIENT_SECRET`, and `GOOGLE_OAUTH_CLIENT_JSON` into
  `env/.env`, prepares the repo-local CLI token path, and prepares the
  repo-local MCP credentials directory.
- Then run `uv run aeat doctor` to verify the active path. Run
  `just gcloud-auth` only if you still need the legacy ADC-backed
  wrapper path.
- `uv run aeat oauth-client init` still exists as the low-level
  compatibility helper, but the normal Kent-facing path is
  `uv run aeat auth init`.
- If `aeat doctor` reports a required `Drive round-trip` failure with a
  stale Desktop OAuth token, rerun
  `uv run aeat auth init --path desktop-oauth-local-dev --reset-cli-token`
  and complete the fresh browser consent flow.

Legacy wrappers stay wrappers:

- `just bootstrap` wraps dependency sync, env setup, the local Google
  auth chain, API enablement, `aeat bootstrap`, and `aeat doctor`.
- `just gsuite-bootstrap` wraps `just gcloud-auth`,
  `just gsuite-enable-apis`, `aeat bootstrap`, and `aeat doctor`.

Neither wrapper creates the Desktop OAuth client on your behalf; the
Cloud Console step is still manual.

### Service-account automation

Set `GOOGLE_APPLICATION_CREDENTIALS` in `env/.env` to a JSON key file
for CI, cron, Cloud Functions, or other headless automation:

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

The legacy `just gsuite-bootstrap-sa` recipe is also a wrapper. It
creates the service account, downloads `env/sa.json`, enables the
required APIs, then runs `aeat bootstrap` and `aeat doctor`. It still
assumes an operator already has `gcloud` access with permission to
create IAM resources.

## Consumer Gmail vs Workspace tenancy

The bootstrap pipeline works on both consumer Google accounts
(`@gmail.com`) and Google Workspace tenants, but the service-account
path has one hard limitation worth knowing up front:

**Service accounts on consumer Gmail have zero Drive storage quota.**

That means the service-account automation path can succeed for IAM,
Service Usage, Cloud Storage / Functions / Run, but
Drive/Sheets/Docs operations under that identity return
`storageQuotaExceeded`. The bootstrap exits with a clear message
pointing at the workaround. For consumer Gmail, and for most local
development, use the Desktop OAuth local-dev path:

```sh
uv run aeat auth init --path desktop-oauth-local-dev
uv run aeat auth init --path desktop-oauth-local-dev --json <downloaded-json>
uv run aeat doctor                      # verify the Desktop OAuth path
just gsuite-enable-apis                 # wrapper: Service Usage sub-step
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
