# aeat

[![CI](https://github.com/wgergely/aeat/actions/workflows/ci.yml/badge.svg)](https://github.com/wgergely/aeat/actions/workflows/ci.yml)

Spanish tax authority (AEAT) automation — tax information retrieval and
filing tools, built on top of Google Workspace and GCP for storage,
auditing, and orchestration.

## Requirements

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) package manager
- [Google Cloud CLI](https://cloud.google.com/sdk/docs/install) (`gcloud`) — `just gsuite-bootstrap` will install it for you on a fresh workstation
- A Google Cloud project ID you control (and a Google account with edit access to it)

## Vanilla-workstation bootstrap

A fresh clone is one command away from a fully-functional Google
Workspace + GCP integration. The `just bootstrap` recipe drives the
whole thing:

```sh
git clone https://github.com/wgergely/aeat
cd aeat

# 1. install deps, vaultspec, env/.env, then run the gsuite pipeline
just bootstrap
```

`just bootstrap` performs, in order:

1. `uv sync` to install runtime + dev dependencies into `.venv/`.
2. `uv run vaultspec-core install --upgrade` to (re-)seed the vaultspec
   framework files.
3. `just env-setup` to copy `env/.env.example` to `env/.env` if missing.
4. `just gsuite-bootstrap`, which is itself five steps:
   - `just gcloud-install` — install or update the Google Cloud CLI
     (handles the Windows bundled-Python non-interactive trap).
   - `just gcloud-auth` — opens a browser, runs `gcloud auth login`,
     `gcloud config set project ${GOOGLE_CLOUD_PROJECT}`, and
     `gcloud auth application-default login` with the locked Drive /
     Sheets / Docs / cloud-platform / userinfo.email scope set.
   - `just gsuite-enable-apis` — enables the eight Google APIs the CLI
     depends on (Drive, Sheets, Docs, Cloud Functions, Cloud Run,
     Storage, IAM, Service Usage).
   - `uv run aeat bootstrap` — locates or creates the scratch resource
     set (`aeat-scratch` Drive folder + `aeat-scratch-sheet` +
     `aeat-scratch-doc`) and writes their IDs back into `env/.env`.
   - `uv run aeat doctor` — runs the read-only health check (see
     below). Exits non-zero on any required failure.

You will need to:

- Edit `env/.env` after `env-setup` and set `GOOGLE_CLOUD_PROJECT` to
  your project ID before re-running `just gsuite-bootstrap`. The
  pipeline fails fast if this value is empty.
- Click through two browser flows during `just gcloud-auth`: one for
  `gcloud auth login`, one for `gcloud auth application-default login`.

## CLI surface

Once bootstrap finishes you have an `aeat` command on PATH (via the
`uv run` shim). The full surface:

```
aeat doctor                          # full health check, exits non-zero on failure
aeat bootstrap                       # provision scratch resources idempotently

aeat drive ls [--folder ID]
aeat drive find QUERY                # raw Drive q= syntax
aeat drive cat FILE_ID [--export-mime MIME]
aeat drive put LOCAL [--folder ID] [--name N] [--mime MIME]
aeat drive mkdir NAME [--parent ID]
aeat drive rm FILE_ID [--permanent]

aeat sheets get SPREADSHEET RANGE
aeat sheets set SPREADSHEET RANGE VALUES_JSON [--raw]
aeat sheets append SPREADSHEET RANGE VALUES_JSON [--raw]
aeat sheets new TITLE
aeat sheets tabs SPREADSHEET

aeat docs get DOC_ID [--plaintext]
aeat docs new TITLE
aeat docs append DOC_ID TEXT
aeat docs replace DOC_ID OLD NEW

aeat cloud functions list
aeat cloud functions describe NAME
aeat cloud run list
aeat cloud run describe SERVICE
aeat cloud storage buckets
aeat cloud storage ls BUCKET [--prefix P]

aeat oauth-client init [--json PATH]    # walk through Cloud Console OAuth Desktop client setup
```

`uv run aeat --help` (and `--help` on any sub-command) prints the
authoritative version.

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

### CI

Every pull request and push to `main` is automatically verified on GitHub Actions across a matrix of Ubuntu and Windows runners. The workflow executes the same checks as the local development loop (`lint`, `typecheck`, `test`, `hooks`). Live tests are explicitly skipped on CI to ensure the build remains secret-free and deterministic.

## License

Apache 2.0 — see [LICENSE](LICENSE).
