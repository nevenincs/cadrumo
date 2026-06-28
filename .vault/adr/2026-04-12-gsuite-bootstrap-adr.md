---
tags:
  - "#adr"
  - "#gsuite-bootstrap"
date: 2026-04-12
modified: '2026-04-12'
related:
  - "[[2026-04-12-gsuite-bootstrap-research]]"
  - "[[2026-04-12-dev-scaffolding-plan]]"
  - "[[2026-04-12-dev-scaffolding-adr]]"
---

# gsuite-bootstrap adr: vanilla-workstation google workspace integration | (**status:** `accepted`)

## Problem Statement

A developer cloning the repository onto a vanilla Windows or Unix
workstation has no path to a working Google Workspace integration. The
existing scaffolding installs a Python `auth.py` resolver and an
incomplete `just gcloud-setup` recipe that only updates the gcloud
binary. There is no CLI surface, no API enablement, no Application
Default Credentials acquisition with the correct scopes, no Drive /
Sheets / Docs / Cloud Functions / Cloud Run / Cloud Storage helpers,
no doctor command, and no live smoke tests. The bootstrap step is
silent, leaves the developer guessing whether anything was set up, and
fails non-obviously on Windows because the gcloud bundled Python refuses
to run non-interactively.

The architectural problem: define one canonical, auditable, end-to-end
path from "fresh git clone" to "I can read and write Drive, Sheets,
Docs from a CLI command and verify it with live smoke tests against
scratch resources I did not have to provision by hand."

## Considerations

Drawn from `<Research>` (`[[2026-04-12-gsuite-bootstrap-research]]`):

- Three credential paths exist (service account, OAuth 2.0 Desktop, ADC).
  Only ADC is acquirable in one browser flow with zero manual Console
  steps. OAuth Desktop requires the developer to create a client in the
  Cloud Console UI — there is no public API or gcloud command for that.
- gcloud's bundled Python on Windows refuses to update / authorise / run
  most subcommands in non-interactive mode unless `CLOUDSDK_PYTHON` is
  pre-set to the copied bundled interpreter.
- Workspace APIs (Drive v3, Sheets v4, Docs v1) are exposed via the
  generic `googleapiclient.discovery` library; GCP product APIs (Cloud
  Functions v2, Cloud Run v2, Cloud Storage) have dedicated
  `google-cloud-*` clients that Google itself recommends for typed
  access.
- ADC's default scope set is `openid, cloud-platform, userinfo.email,
  sqlservice.login` — it does **not** include Drive, Sheets, Docs.
  Explicit `--scopes` must be passed at `application-default login` time.
- gcloud writes a quota project into ADC iff `gcloud config set project`
  ran first. Order matters.
- Refresh-token quota (per-(client, user)) makes shared OAuth Desktop
  clients risky in a multi-developer setting; ADC sidesteps it.
- Domain-wide delegation requires Workspace tenancy and only works on
  service-account credentials. Out of band for vanilla-workstation
  bootstrap but must remain supported in code.
- Live tests must use real APIs and never mocks per project rules,
  which forces an idempotent scratch-resource lifecycle that the
  bootstrap itself provisions.
- `aeat doctor` must be the single source of truth for "is my
  workstation actually set up", and it must report enough granularity
  that a failing row points to a specific fix.

Tech / libraries considered:

- **CLI framework**: Typer vs Click. Typer is type-hint-driven, single
  decorator per command, ships rich-based help, and the Python ecosystem
  around Google Cloud uses it. Click is more verbose; we do not need its
  plugin ecosystem.
- **Drive/Sheets/Docs SDK**: `googleapiclient.discovery` (chosen) vs
  per-product wrappers (`google-cloud-drive` etc., which are
  Workspace-only and incomplete).
- **GCP SDK**: dedicated `google-cloud-functions`,
  `google-cloud-run`, `google-cloud-storage` clients (chosen) vs
  discovery layer (rejected — generic and verbose).
- **gcloud cross-platform driver**: justfile recipes with `[unix]` and
  `[windows]` bodies (chosen — already in tree) vs a Python wrapper
  around gcloud (rejected — adds an interpreter to the bootstrap critical
  path).
- **Token cache location**: project `.tokens/` (existing) vs the gcloud
  well-known ADC path (chosen for ADC, since that's where libraries
  look). Both coexist: `.tokens/` is for OAuth Desktop, ADC lives in its
  well-known place managed by gcloud.
- **Live test isolation**: per-test UUID prefixes (chosen) vs per-run
  scratch sub-folders (deferred until parallel runs actually conflict).

## Constraints

- Python 3.13, uv, hatchling, src layout. No new package managers.
- Cross-platform: Windows pwsh and Unix bash must both work end-to-end.
- All env vars must be defined in `src/aeat/config.py` Settings; the
  alignment test in `tests/test_config.py` enforces this against
  `env/.env.example`.
- ty (not mypy), prek (not pre-commit). No skips on lint/type checks.
- Pytest markers `@pytest.mark.unit` / `@pytest.mark.live` mandatory.
  Live tests must never use mocks/fakes/stubs/patches.
- Google-style docstrings + type hints on all public signatures.
- Branch naming `<type>/<issuenum>-<subject>`. Stays on
  `chore/4-dev-scaffolding`.
- The user is autonomous-mode: no human-in-the-loop approvals between
  pipeline phases. The pipeline runs research → adr → plan → execute →
  review without pausing.
- Nothing is deferred. The execution phase produces working code,
  passing unit tests, passing live tests against the scratch resources
  the bootstrap provisions, an updated doctor, an updated bootstrap
  recipe, and a code review record before this feature is considered
  complete.

## Implementation

High-level shape, broken by domain. Each domain becomes a phase block in
the `<Plan>`.

### a. configuration surface

Extend `Settings` in `src/aeat/config.py` with the new env vars the
bootstrap reads and writes:

- `aeat_scratch_folder_id` — Drive folder for scratch resources.
- `aeat_scratch_sheet_id` — scratch Sheet ID.
- `aeat_scratch_doc_id` — scratch Doc ID.
- `aeat_live_tests_enabled` — bool, defaults false; gating flag.

Update `env/.env.example` with documented placeholders. The alignment
test must pass.

Add an `env/.env` writer helper in a new `src/aeat/env_io.py`. It
reads/writes `KEY=VALUE` lines preserving comments and blank lines,
because the bootstrap mutates `env/.env` to persist scratch IDs. Pure
unit-tested module.

### b. auth module updates

`src/aeat/auth.py`:

- Add `DOCS_SCOPE` to scope constants and to the default `SCOPES` list.
- Add `build_docs_service`, `build_storage_service`,
  `build_cloudfunctions_service`, `build_cloudrun_service` builders. The
  Workspace builders use `discovery.build(..., cache_discovery=False)`;
  the Cloud builders use the dedicated `google-cloud-*` clients.
- Add an `assert_credentials_have_scopes(creds, required: list[str])`
  helper that doctor uses to verify ADC was acquired with the right
  scope set.
- Existing OAuth Desktop and Service Account paths kept; resolver order
  unchanged.

### c. cli surface

New package `src/aeat/entrypoints/cli/` with Typer sub-apps:

- `__main__.py` — root `aeat` Typer app, wires sub-apps.
- `doctor.py` — `aeat doctor`. Read-only health table covering env file,
  gcloud CLI, gcloud auth, ADC + scope verification, service account
  (advisory), OAuth Desktop (advisory), API enablement (Service Usage),
  per-surface round-trip (`drive.about().get`,
  `sheets.spreadsheets.get` against scratch ID,
  `docs.documents.get` against scratch ID, Cloud
  Functions/Run/Storage list calls). Exits non-zero on any required
  MISSING. Uses rich for the table.
- `bootstrap.py` — `aeat bootstrap`. Drives the post-gcloud half:
  validates ADC, validates API enablement, creates scratch resources
  idempotently by name, writes their IDs back to `env/.env`.
- `drive.py` — `aeat drive ls|cat|put|rm|mkdir|find`. Implements the
  Drive search-query language for `find`, supports parent folder
  filtering. `cat` exports Workspace docs to plaintext where possible.
- `sheets.py` — `aeat sheets get|set|append|new|tabs`.
- `docs.py` — `aeat docs get|new|append`. The `append` builds Docs
  batchUpdate requests in reverse-document-order via a helper.
- `cloud.py` — `aeat cloud functions list|describe`,
  `aeat cloud run list|describe`, `aeat cloud storage buckets|ls`.
- `oauth.py` — `aeat oauth-client init`. Prints the deep-link Console
  URL, the required redirect URI, the scope set, prompts for the
  downloaded JSON path, parses, writes `GOOGLE_OAUTH_CLIENT_ID` /
  `GOOGLE_OAUTH_CLIENT_SECRET` into `env/.env`. Off the critical path
  but shipped.

Pyproject:

```toml
[project.scripts]
aeat = "aeat.entrypoints.cli.__main__:app"
```

### d. justfile recipes

Replace and extend the existing recipes:

- `gcloud-install` — install or update; rename of the current
  `gcloud-setup` recipe. Cross-platform with `CLOUDSDK_PYTHON` pre-set.
- `gcloud-auth` — runs `gcloud auth login`,
  `gcloud config set project`, then
  `gcloud auth application-default login --scopes=...` with the locked
  scope set. Reads `GOOGLE_CLOUD_PROJECT` from `env/.env`; fails loudly
  if empty.
- `gsuite-enable-apis` — `gcloud services enable drive.googleapis.com
  sheets.googleapis.com docs.googleapis.com cloudfunctions.googleapis.com
  run.googleapis.com storage.googleapis.com iam.googleapis.com
  serviceusage.googleapis.com`.
- `gsuite-bootstrap` — composes `gcloud-install`, `gcloud-auth`,
  `gsuite-enable-apis`, then `uv run aeat bootstrap`, then
  `uv run aeat doctor`. **Single command end-to-end**, prints a
  before/after report at every step.
- `gsuite-doctor` — `uv run aeat doctor` shortcut.
- `gsuite-oauth-client` — `uv run aeat oauth-client init`.
- `test` — unchanged (skips live).
- `test-live` — `uv run pytest -m live`.

The existing `bootstrap` recipe gets one extra final line that runs
`gsuite-bootstrap`, so `just bootstrap` on a fresh worktree does
**everything**.

### e. live smoke tests

Co-located per CLAUDE.md:

- `src/aeat/entrypoints/cli/_test_drive_live.py` — round-trip: create temp file
  with UUID prefix in scratch folder, list, fetch metadata, download,
  delete. `@pytest.mark.live`.
- `src/aeat/entrypoints/cli/_test_sheets_live.py` — set range, append, get, clear.
- `src/aeat/entrypoints/cli/_test_docs_live.py` — append text, get, verify
  presence, delete inserted range.
- `src/aeat/entrypoints/cli/_test_cloud_live.py` — list functions, list run
  services, list storage buckets — assert the calls return without auth
  errors. No deploy.
- A shared `src/aeat/entrypoints/cli/_live.py` module exposes a `scratch` fixture
  and skip-if-disabled helper.

`pyproject.toml` `[tool.pytest.ini_options]`:

```toml
markers = [
    "unit: deterministic tests with no external I/O",
    "live: tests that hit real Google APIs against scratch resources",
]
addopts = "-v --tb=short -m 'not live'"
```

### f. doctor decision matrix

| Section          | Required | Check                                                                   |
| ---------------- | -------- | ----------------------------------------------------------------------- |
| env/.env present | yes      | file exists, parses                                                     |
| GOOGLE_CLOUD_PROJECT | yes  | non-empty in Settings                                                   |
| gcloud binary    | yes      | on PATH, version printable                                              |
| gcloud auth      | yes      | one ACTIVE account                                                      |
| gcloud project   | yes      | matches `GOOGLE_CLOUD_PROJECT`                                          |
| ADC file         | yes      | well-known path exists, JSON parses                                     |
| ADC scopes       | yes      | superset of Drive/Sheets/Docs/cloud-platform/userinfo.email             |
| API enablement   | yes      | drive, sheets, docs, cloudfunctions, run, storage, iam, serviceusage    |
| Drive round-trip | yes      | `about().get(fields="user")` returns 2xx                                |
| Sheets round-trip| yes      | `spreadsheets.get(scratch sheet)` 2xx (skipped if no scratch ID yet)    |
| Docs round-trip  | yes      | `documents.get(scratch doc)` 2xx (skipped if no scratch ID yet)         |
| Functions list   | yes      | empty list is OK                                                         |
| Run list         | yes      | empty list is OK                                                         |
| Storage list     | yes      | empty list is OK                                                         |
| Service account  | no       | if env set, file readable + parses                                       |
| OAuth Desktop    | no       | if both env set, optional cached token validity                          |
| Live tests       | no       | reports `AEAT_LIVE_TESTS_ENABLED` flag value                             |

## Rationale

ADC is the choice that makes vanilla-workstation bootstrap actually
vanilla: one browser flow handles every Google client library, refresh
tokens are managed by Google, the quota project is captured at login,
and there is no Console-side manual step. The other two paths exist for
real reasons (CI, server impersonation) but neither survives the
"vanilla developer with no prior context" test.

The fixed gcloud command order (set project before
application-default login, with explicit scopes) was the single biggest
sharp edge surfaced in research — getting it wrong silently produces an
ADC file that omits the Workspace scopes, and every subsequent Drive/
Sheets/Docs call returns 403. Encoding the order in a justfile recipe
that always runs them in that sequence is the simplest way to make
"wrong" unreachable.

Pre-setting `CLOUDSDK_PYTHON` once per pwsh recipe block (not per
gcloud call) trades a tiny amount of recipe verbosity for guaranteed
non-interactive operation across every gcloud subcommand we invoke. We
already learned the cost of skipping it on `components update`; the
research confirmed the same applies to `auth login` and `services
enable`. Doing it once at the top of every recipe block costs nothing.

Splitting Workspace and GCP SDKs along the
`googleapiclient.discovery` / `google-cloud-*` line is what Google's
own current docs recommend, and lets us write thinner code on the GCP
side (typed clients) while keeping uniform shape on the Workspace side
where dedicated clients do not exist. The decision to pass
`cache_discovery=False` everywhere is defensive — the discovery cache
has been a long-standing source of intermittent test failures, and the
cost of disabling it is one network round-trip per `discovery.build`,
which we can amortise by building services lazily and once.

Typer is a one-line decision: type hints become CLI flags, rich help
ships out of the box, the `aeat` entry point is one `pyproject.toml`
line. We get a coherent CLI surface for the cost of a single new
dependency.

`aeat doctor` is the linchpin that makes the whole feature debuggable.
By giving every check its own row and a per-row remediation hint
(deferred to the implementation, but the row labels above already
imply the fix), we replace "the bootstrap exited silent and I have no
idea what state I'm in" with a deterministic table. Doctor exits
non-zero on any required missing row so it is CI-usable as a
gating step.

Idempotent name-based scratch resource creation, with the IDs persisted
to `env/.env`, gives live tests real targets without the developer
having to create anything by hand. The name-based dedup means re-running
`aeat bootstrap` on a workstation that already ran it once is a no-op
on the API side and only re-writes the same env values.

The choice not to defer **anything** is the user's explicit instruction.
The plan that follows enumerates every step and the execute phase will
land them all on `chore/4-dev-scaffolding` before code review.

## Consequences

- New runtime dependencies: `typer`, `rich` (already a Typer transitive
  but pinned for clarity), `google-cloud-functions`, `google-cloud-run`,
  `google-cloud-storage`. All four are first-party Google or
  well-maintained. Lockfile churn expected.
- New entry point `aeat` in `pyproject.toml`. Users get a global CLI on
  `uv sync`.
- `Settings` grows by four fields. Every new field has a default and a
  documented entry in `env/.env.example`; the alignment test enforces
  this.
- `env/.env` is now a **mutable** file, not just a template-derived
  copy. The bootstrap writes scratch IDs back into it. The env writer
  helper must preserve comments and ordering. Risk: developer-edited
  comments in `env/.env` survive, but two parallel bootstraps could
  race on the file. Mitigation: bootstrap is single-process, runs
  serially; we accept the small race window.
- Live tests now talk to real Google APIs. They are gated behind
  `AEAT_LIVE_TESTS_ENABLED=true` in `env/.env` plus the presence of
  scratch IDs. Default `pytest` invocation continues to skip them via
  the `-m 'not live'` addopts. CI must opt in explicitly.
- Quota: Drive/Sheets/Docs API quotas are per-user-per-100s and are
  generous; live test round-trips will not hit them under normal
  development. No further action.
- Failure modes the doctor will surface but not auto-fix: missing
  Workspace tenancy for DWD, expired refresh tokens (re-run
  `gcloud auth application-default login`), revoked client credentials,
  project moved between billing accounts. Doctor reports; the developer
  re-runs the relevant recipe.
- Future work that becomes possible after this lands: deploy smoke for
  Cloud Functions/Run, Workspace admin scopes for org-wide automation,
  Forms / Calendar / Gmail integration (each is one new sub-app under
  `aeat cli`).
- The OAuth Desktop client init helper gives developers a guided path
  if they ever need user-delegated scopes that ADC cannot grant
  (Workspace admin, Gmail send-as, etc.). It is shipped but not on the
  critical path.
- One-shot rollback: every change is on `chore/4-dev-scaffolding`.
  Revert the branch to drop the entire feature.
