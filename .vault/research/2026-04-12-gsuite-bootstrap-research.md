---
tags:
  - "#research"
  - "#gsuite-bootstrap"
date: 2026-04-12
modified: '2026-04-12'
related:
  - "[[2026-04-12-dev-scaffolding-plan]]"
  - "[[2026-04-12-dev-scaffolding-adr]]"
  - "[[2026-04-12-dev-scaffolding-research]]"
---

# gsuite-bootstrap research: vanilla-workstation google workspace integration

Research grounding the implementation of a fully-automated Google Workspace
bootstrap pipeline. Goal: a developer on a vanilla Windows or Unix
workstation runs a single command, walks through one browser auth flow,
and ends up with a working CLI capable of reading and writing Drive,
Sheets, Docs and inspecting Cloud Functions / Cloud Run / Cloud Storage.
Live smoke tests run against scratch resources the bootstrap creates
itself, never against production data.

Sources: Context7 (`/googleapis/google-api-python-client`,
`/websites/googleapis_dev_python_google-auth`,
`/websites/cloud_google_sdk_gcloud_reference_auth`) plus prior on-disk
`src/aeat/auth.py` and `src/aeat/config.py`. Items not directly cited
from current docs are marked **[training-data]** and must be re-verified
during execution before being trusted on a sharp edge.

## Findings

### 1. gcloud bootstrap sequence

A reliable end-to-end gcloud bootstrap on both platforms is a fixed
sequence of commands, each with a non-interactive flag and a deterministic
verification step. The Windows-specific bundled-Python issue already
encountered with `components update` extends to **every** gcloud command
that invokes the bundled Python interpreter — `auth login`,
`application-default login`, and `services enable` are all affected when
run from non-interactive shells. The fix is the same:

1. Resolve the bundled interpreter once via
   `gcloud components copy-bundled-python` and export `CLOUDSDK_PYTHON`
   for the rest of the session.
2. Then run gcloud commands.

The canonical sequence becomes:

- `gcloud components copy-bundled-python` → set `CLOUDSDK_PYTHON`
  *(Windows only; harmless to skip on Unix)*
- `gcloud components update --quiet` (idempotent, already implemented)
- `gcloud auth login --update-adc=false --quiet` — establishes a user
  identity for the gcloud CLI itself. Browser opens; user consents.
  Stored under `gcloud config configurations`.
- `gcloud config set project ${GOOGLE_CLOUD_PROJECT}` — fails loudly if
  the env var is empty (deliberate, see decisions).
- `gcloud auth application-default login` — separate browser flow that
  writes ADC JSON to the well-known path
  (`%APPDATA%\gcloud\application_default_credentials.json` on Windows,
  `~/.config/gcloud/application_default_credentials.json` on Unix).
  This is the credential picked up by `google.auth.default()`.
- `gcloud services enable drive.googleapis.com sheets.googleapis.com
  docs.googleapis.com cloudfunctions.googleapis.com run.googleapis.com
  storage.googleapis.com iam.googleapis.com serviceusage.googleapis.com`
  — multi-arg form is documented and idempotent. `serviceusage` itself
  must be enabled before we can list enablement state programmatically.

Headless / no-browser variants exist: `--no-launch-browser` (and the
newer `--no-browser` alias) on both `auth login` and
`application-default login`. They print a URL the user pastes into a
browser on another machine and an authorization code prompt back on the
gcloud machine. We do not need this for vanilla-workstation use but we
should expose it as a flag for SSH / WSL bootstrap scenarios.

**Sharp edge**: `gcloud auth application-default login` writes a quota
project into the ADC JSON if one is set in `gcloud config`, **unless**
`--disable-quota-project` is passed or a `--client-id-file` is supplied.
We want quota project written so library calls are billed to the right
project — order matters: run `gcloud config set project` *before*
`application-default login` so the quota project is captured at ADC
acquisition time.

**Sharp edge**: ADC scopes default to
`openid, cloud-platform, userinfo.email, sqlservice.login`. That set
**does not** include the Drive/Sheets/Docs scopes. For ADC to work
against Drive/Sheets/Docs the libraries either (a) request the scopes at
service-build time and the user has already consented (which ADC does
not natively cover for these scopes), or (b) you log in with explicit
`--scopes`. We must pass
`--scopes=https://www.googleapis.com/auth/cloud-platform,https://www.googleapis.com/auth/drive,https://www.googleapis.com/auth/spreadsheets,https://www.googleapis.com/auth/documents`
to the `application-default login` step. Documented behaviour confirmed
via Context7.

### 2. Auth model per surface

Three credential paths are already implemented in `src/aeat/auth.py`.
Mapping them to the surfaces we care about, with current-doc backing:

| Surface          | Preferred dev | Preferred prod | Notes                                                                                                  |
| ---------------- | ------------- | -------------- | ------------------------------------------------------------------------------------------------------ |
| Drive v3         | ADC           | Service acct   | ADC works once explicit scopes were granted at login time. SA requires DWD for non-owner content.      |
| Sheets v4        | ADC           | Service acct   | Same as Drive.                                                                                         |
| Docs v1          | ADC           | Service acct   | Same as Drive. **[training-data]**: docs API is the smallest of the three and has fewer quota knobs.   |
| Cloud Functions  | ADC           | Service acct   | `cloud-platform` scope is sufficient for list/get; deploy needs `cloudfunctions.developer` IAM role.   |
| Cloud Run        | ADC           | Service acct   | Same. Read needs `run.viewer`, deploy needs `run.developer`.                                           |
| Cloud Storage    | ADC           | Service acct   | `devstorage.full_control` or scoped variants; ADC `cloud-platform` covers it for dev.                  |

**Decision**: ADC is the canonical dev path, period. OAuth 2.0 Desktop
flow remains supported in `auth.py` but we deprecate it as the *primary*
entry point for new code. Reasons:

- ADC gives us one browser flow that all Google client libraries pick up
  with zero extra config.
- OAuth Desktop client requires the user to manually create a client in
  Cloud Console and paste two strings into `env/.env`, which is exactly
  the friction we are removing.
- Service accounts remain the future server/CI path and stay in code,
  but are not part of vanilla-workstation bootstrap.

**Workspace vs consumer Gmail**: domain-wide delegation (`with_subject`
in `auth.py`) requires Workspace admin enrolment and only works for
service-account credentials, never for ADC or installed-app OAuth. We
gate any DWD code path behind `GOOGLE_IMPERSONATE_EMAIL` being set, and
in `doctor` we report the limitation rather than trying to detect
Workspace tenancy automatically (no API short of touching Admin SDK,
which itself needs DWD — chicken-and-egg).

### 3. SDK choice per surface

Confirmed via Context7 against current `google-api-python-client` docs:

- **Drive v3** — `googleapiclient.discovery.build("drive", "v3", credentials=creds)`.
  - Create file: `service.files().create(body=metadata, media_body=MediaFileUpload(...), fields="id,name").execute()` — supports resumable upload, max 5,120 GB.
  - Export Workspace docs: `service.files().export_media(fileId=..., mimeType=...)` paired with `MediaIoBaseDownload`. Export is capped at 10MB; for larger docs we must use the Drive download endpoint after copying.
  - List/search: `service.files().list(q=..., pageSize=..., fields="...")` with the Drive search query language (`name contains 'x'`, `mimeType='...'`, `parents in '...'`, `trashed=false`).
- **Sheets v4** — `googleapiclient.discovery.build("sheets", "v4", credentials=creds)`.
  - Read: `spreadsheets.values.get(spreadsheetId, range)` returns A1-noted range.
  - Write: `spreadsheets.values.update(spreadsheetId, range, body, valueInputOption="RAW"|"USER_ENTERED")`.
  - Append: `spreadsheets.values.append(spreadsheetId, range, body, valueInputOption=..., insertDataOption="INSERT_ROWS")`.
  - Bulk: `spreadsheets.values.batchUpdate` accepts a list of `ValueRange` objects, each with `range`, `majorDimension`, `values`.
  - Structural: `spreadsheets.batchUpdate` (not the values one) for adding/renaming sheets, formatting, etc.
- **Docs v1** — `googleapiclient.discovery.build("docs", "v1", credentials=creds)`.
  - Read: `documents.get(documentId).execute()` returns the full body tree.
  - Write: `documents.batchUpdate(documentId, body={"requests": [...]})` with `insertText`, `updateTextStyle`, `createParagraphBullets`, etc. **All edits are atomic** — a batch is all-or-nothing, which is the right shape for transactional writes.
- **Cloud Functions / Cloud Run / Cloud Storage** — these have **two** Python SDK options each:
  1. The `google-api-python-client` discovery layer — uniform shape with Drive/Sheets/Docs but generic and verbose.
  2. The dedicated `google-cloud-functions`, `google-cloud-run`, `google-cloud-storage` clients — typed, domain-specific, and the path Google itself recommends for GCP product APIs **[training-data]**.
  - **Decision**: discovery layer for Workspace APIs (Drive/Sheets/Docs), dedicated `google-cloud-*` clients for Cloud APIs. This is the documented split — Workspace APIs were never moved to dedicated clients, GCP product APIs were.

**Pinning**: every google-api-python-client call should pass `cache_discovery=False` (the discovery cache is the source of countless intermittent test failures **[training-data]**). The `static_discovery` mode introduced in 2.x ships baked discovery docs and should be preferred where available.

### 4. Scope matrix

| Use case                                  | Scope                                                            |
| ----------------------------------------- | ---------------------------------------------------------------- |
| Read+write Drive (incl. Workspace native) | `https://www.googleapis.com/auth/drive`                          |
| Read+write Sheets                         | `https://www.googleapis.com/auth/spreadsheets`                   |
| Read+write Docs                           | `https://www.googleapis.com/auth/documents`                      |
| GCP admin (Functions/Run/Storage/Service usage) | `https://www.googleapis.com/auth/cloud-platform`           |
| Identity (always, for ADC quota project)  | `openid`, `https://www.googleapis.com/auth/userinfo.email`       |

Narrower constants exported for future hardening but not used by the
default bootstrap:

- `drive.readonly`, `drive.file`, `drive.metadata.readonly`
- `spreadsheets.readonly`
- `documents.readonly`
- `devstorage.read_only`

The existing `SCOPES` constant in `src/aeat/auth.py` is missing the
`documents` scope and must be updated.

### 5. API enablement

Programmatic enablement detection is via the **Service Usage API**
(`serviceusage.googleapis.com`) — itself which must be enabled first
(but is on by default for any project that has *any* API enabled, so
this is a non-issue in practice). Listing enabled services:

- REST: `GET https://serviceusage.googleapis.com/v1/projects/{project}/services?filter=state:ENABLED`
- Python: via `googleapiclient.discovery.build("serviceusage", "v1")` then
  `service.services().list(parent=f"projects/{project}", filter="state:ENABLED")`.

Bootstrapping is faster via the gcloud CLI (`gcloud services enable ... --async` then poll) than via the API, so the recipe uses gcloud, but **doctor** checks state via the Service Usage API directly so it works without gcloud installed in CI.

**Cost implications**: enabling Drive/Sheets/Docs/Service Usage costs nothing. Cloud Functions / Cloud Run / Cloud Storage have a generous free tier — listing/metadata calls are free. **Deploying** anything is what costs money. Bootstrap performs no deploys.

### 6. Doctor / status check design

`aeat doctor` reports a table of states across three axes. Each row is one of `OK / MISSING / WARN`. The shape:

| Section          | Check                                                                                      | OK signal                                              |
| ---------------- | ------------------------------------------------------------------------------------------ | ------------------------------------------------------ |
| env file         | `env/.env` exists, `GOOGLE_CLOUD_PROJECT` non-empty                                        | both true                                              |
| gcloud CLI       | binary on PATH, `gcloud config get-value project` matches env                              | both true                                              |
| gcloud auth      | active account present (`gcloud auth list --filter=status:ACTIVE --format='value(account)'`) | one account                                            |
| ADC              | well-known ADC JSON file exists, parses, scopes include the four we need                   | file present + scopes superset of required             |
| service account  | `GOOGLE_APPLICATION_CREDENTIALS` (if set) points at existing readable JSON, parses          | file present and parses; or env unset (skipped)        |
| OAuth Desktop    | client_id+secret both set in env (if either set), token file in `aeat_token_dir` if exists | both set + token valid; or both unset (skipped)        |
| API enablement   | each of drive/sheets/docs/cloudfunctions/run/storage enabled in project                    | all enabled                                            |
| live round-trips | per surface: a no-op call (e.g. `drive.about().get(fields="user")`)                        | call returns 2xx                                       |

`doctor` is read-only and does not mutate any state. It exits non-zero
if any **required** row is `MISSING` (env, gcloud auth, ADC, the four
API enablements). Service account and OAuth Desktop rows are advisory.

### 7. Live smoke test strategy

Constraint: live tests must not pollute production and must never use
mocks. The strategy:

- Bootstrap creates a top-level Drive folder named `aeat-scratch`
  *only if it does not already exist*, owned by the authenticated user.
  Folder ID is written back to `env/.env` as `AEAT_SCRATCH_FOLDER_ID`.
- Inside that folder it creates `aeat-scratch-sheet` (Sheet) and
  `aeat-scratch-doc` (Doc), same idempotency. IDs written as
  `AEAT_SCRATCH_SHEET_ID` and `AEAT_SCRATCH_DOC_ID`.
- Live tests:
  - Skip with a clear message if the relevant `AEAT_SCRATCH_*_ID` is
    unset.
  - Use a per-test-run UUID prefix for any data they write so two
    parallel test runs don't fight.
  - Always teardown what they create (delete files, clear ranges).
  - Use `@pytest.mark.live` exclusively. `@pytest.mark.unit` is the
    other allowed marker per CLAUDE.md.
- A new `live` group in `pyproject.toml` `[tool.pytest.ini_options]`
  configures `markers = ["unit: ...", "live: ..."]` and
  `addopts = "-v --tb=short -m 'not live'"` so default runs skip live
  tests; `just test-live` overrides with `-m live`.

This is the deferred chunk you mentioned — the scratch resource creator
is built now, the per-surface live tests are scaffolded but the
exhaustive matrix is added later. The plan must explicitly mark this.

### 8. CLI framework

Two real candidates:

- **Typer** — Fast-to-write, type-hint-driven, built on Click, ships
  rich-based help out of the box, well-supported in the Google ecosystem
  (Vertex AI, Cloud Run examples in current docs use it
  **[training-data]**). Single decorator per command. Excellent for our
  shape.
- **Click** — More explicit, more verbose, more mature, larger plugin
  ecosystem. We don't need the plugin ecosystem.

**Decision**: Typer. Single dependency, single import, autocompletion via
`typer install`, type hints become CLI flags for free. Entry point in
`pyproject.toml`:

```toml
[project.scripts]
aeat = "aeat.entrypoints.cli.__main__:app"
```

CLI module layout:

```
src/aeat/entrypoints/cli/
  __init__.py
  __main__.py        # typer.Typer() instance + sub-apps
  doctor.py          # aeat doctor
  bootstrap.py       # aeat bootstrap (calls gcloud + scratch creation)
  drive.py           # aeat drive ls|cat|put|rm|mkdir
  sheets.py          # aeat sheets get|set|append|new
  docs.py            # aeat docs get|new|append
  cloud.py           # aeat cloud functions|run|storage list
```

### 9. OAuth Desktop client bootstrap

What can be automated: nothing. There is no public REST or gcloud
command that creates an OAuth 2.0 client ID for a project. The
documented path is the Cloud Console UI → APIs & Services → Credentials
→ Create OAuth client. **[training-data]**: this has been a long-standing
gap; the closest is the workforce/workload identity federation flow
which is unrelated.

What we *can* do: detect that the user has not configured an OAuth
Desktop client and tell them exactly what to click. A `just gsuite-oauth-client`
helper that prints:

- the exact Console URL (deep-linking to the credentials page for the
  active project),
- the client type to choose ("Desktop app"),
- the redirect URI (`http://localhost:8080`),
- the scopes that will be requested,
- a prompt for the path of the downloaded JSON,
- and writes `GOOGLE_OAUTH_CLIENT_ID` / `GOOGLE_OAUTH_CLIENT_SECRET`
  into `env/.env` from the parsed JSON.

This stays in the codebase but is **not on the critical path** for
vanilla-workstation bootstrap, because ADC handles the dev case.

### 10. Sharp edges and gotchas

- **Refresh token quota**: Google enforces a per-(client, user) refresh
  token cap (training-data: ~100). OAuth Desktop flow with a shared
  client_id across many devs hits this. ADC sidesteps it because each
  ADC login uses a separate Google-managed client.
- **Token expiration during long flows**: `google-auth` automatically
  refreshes via `creds.refresh(Request())` if a `refresh_token` is
  present and `creds.expired`. ADC and OAuth Desktop both have refresh
  tokens; service account JWTs are minted on demand.
- **`gcloud auth login` vs `gcloud auth application-default login`**:
  these are *separate* token stores. The first authenticates the
  `gcloud` CLI itself. The second authenticates Google client libraries.
  Doing one does not do the other. Doctor must check both.
- **Discovery cache flakiness**: pass `cache_discovery=False` to
  `discovery.build` or use the static discovery shipped in
  google-api-python-client 2.x.
- **Workspace admin scopes**: `https://www.googleapis.com/auth/admin.*`
  scopes require Workspace admin and DWD. Out of scope for this feature.
- **Docs API parameter order**: `documents.batchUpdate` requests are
  index-based and indices shift as earlier requests are applied. Always
  build text-insertion batches in **reverse document order** to keep
  indices stable. **[training-data]** — verify against current Docs v1
  docs at execution time.
- **Drive `q` query escaping**: single-quoted strings inside the query
  must escape inner single quotes as `\'`. The library does *not* do
  this for you.
- **Sheets value type**: `valueInputOption=USER_ENTERED` makes Google
  parse strings as numbers/dates; `RAW` preserves them. Default to
  `USER_ENTERED` for ergonomic CLI usage; expose `--raw` flag.
- **Service Usage list pagination**: 200-page-size default, must follow
  `nextPageToken`. Doctor must paginate.
- **gcloud bundled-Python**: confirmed for `components update` on
  Windows; assume the same for any gcloud subcommand that does work
  inside the bundled interpreter and pre-set `CLOUDSDK_PYTHON` once at
  the top of every pwsh recipe block.

## Decisions locked by research

1. **ADC is the canonical dev auth.** OAuth Desktop demoted to optional;
   service account remains for server/CI; both stay in code.
2. **gcloud bootstrap order is fixed**: install → update → set project
   → `auth login` → `application-default login` (with explicit scopes
   covering Drive/Sheets/Docs/cloud-platform/userinfo.email) → enable
   APIs.
3. **`CLOUDSDK_PYTHON` pre-set on Windows** once per pwsh recipe block
   via `gcloud components copy-bundled-python`, applied to every gcloud
   call in that block.
4. **Workspace SDKs via `googleapiclient.discovery`** (Drive/Sheets/Docs).
   **GCP SDKs via `google-cloud-functions`, `google-cloud-run`,
   `google-cloud-storage`** dedicated clients.
5. **`cache_discovery=False`** on every `discovery.build` call.
6. **CLI framework: Typer.** Entry point `aeat`, sub-apps per surface.
7. **`aeat doctor` is read-only** and exits non-zero on any required
   `MISSING` row.
8. **Scratch resource creation** is idempotent, name-based, owned by
   the bootstrapping user, IDs persisted to `env/.env`.
9. **Live test marker**: `@pytest.mark.live`, default `pytest` skips
   them, `just test-live` opts in.
10. **API enablement target set**: drive, sheets, docs, cloudfunctions,
    run, storage, iam, serviceusage. All enabled at bootstrap; doctor
    verifies.
11. **OAuth Desktop client provisioning is manual** with a guided
    `just gsuite-oauth-client` helper that does the env-write, but is
    **not on the bootstrap critical path**.
12. **Cloud Functions / Run / Storage**: list-and-describe smoke only;
    no deploy in this feature.
13. **DWD impersonation** stays gated behind `GOOGLE_IMPERSONATE_EMAIL`.
    Doctor reports the gate but does not attempt to validate Workspace
    tenancy.
14. **`SCOPES` constant in `src/aeat/auth.py` updated** to add the
    `documents` scope.
15. **Existing `auth.py` resolver order kept**: SA → OAuth → ADC,
    *because* tests still need to be able to inject SA and OAuth paths;
    bootstrap merely makes the ADC path the easiest one to land in.

## Open questions / deferred

These are not blockers — they become discussion points in the ADR or
items to defer past this feature:

- **Scratch project bootstrap**: should the bootstrap support
  creating a fresh GCP project (`gcloud projects create`) as an opt-in
  flag, or always require `GOOGLE_CLOUD_PROJECT` to pre-exist? Current
  decision: pre-exist. Revisit if vanilla-workstation feedback shows
  project creation friction.
- **Billing account auto-link**: skipped entirely. Cloud Functions/Run
  smoke is read-only; no billing required for that. If we later add
  deploy smoke, billing-account linkage becomes a separate feature.
- **Multi-account / per-profile gcloud configurations**: out of scope.
  We assume a single active gcloud configuration per workstation.
- **Token refresh during long-running CLI commands**: rely on
  `google-auth`'s built-in refresh; revisit if we hit a real failure.
- **Concurrent live test isolation**: per-test UUID prefixes are the
  current plan; if parallel test runs conflict in practice, escalate
  to per-run scratch sub-folders.
- **Docs API reverse-order index stability**: documented as a sharp
  edge but the helper that builds Docs batch requests should encode the
  reverse-order convention as a function rather than relying on caller
  discipline. Belongs to the Docs CLI step in the plan.
- **Static discovery vs dynamic**: assess at execution time whether
  `static_discovery=True` is available for all six services (Drive,
  Sheets, Docs, Cloud Functions, Cloud Run, Cloud Storage). If yes,
  enable it; if not, fall back to `cache_discovery=False`.
