---
tags:
  - '#audit'
  - '#google-oauth'
date: '2026-05-06'
modified: '2026-05-06'
related:
  - "[[2026-05-06-google-oauth-research]]"
  - "[[2026-04-12-google-fixtures-adr]]"
  - "[[2026-04-16-google-workspace-mcp-auth-adr]]"
  - "[[2026-04-21-google-auth-ux-adr]]"
---

# `google-oauth` audit: `google-oauth teardown audit: pre-excision baseline`

## Purpose

Snapshot the on-disk footprint of the discarded `gcloud`-CLI-anchored
Google authentication architecture before the `google-oauth` feature
replaces it with a self-hosted Google OAuth application that targets only
Drive and Sheets read/write. The intent is to give the upcoming ADR and
excision plan a complete, line-counted blast radius so nothing is forgotten
and so reviewers can verify each removal against this ledger. Successor
research lives in the companion document; the upcoming ADR will reference
both.

## Scope

In scope: every Python module, test, settings field, env-var, justfile
recipe, ignore rule, MCP entry, Sphinx page, locale string, and prose
paragraph that exists today because the project committed to the
`gcloud`-bootstrapped Workspace OAuth + Service-Account dual-path
model.

Out of scope and explicitly to be retained:

- The Gemini LLM HTTP client at `src/aeat/adapters/outbound/llm/_providers/gemini.py`
  and the matching `GEMINI` enum entry in `_models.py`. This is a
  pure HTTPS client to the Google Gemini API authenticated via API key; it
  does not touch Workspace, Drive, Sheets, OAuth, or `gcloud`.
- Incidental mentions of Google in AEAT-published HTML fixtures under
  `tests/fixtures/aeat-sede/` and `corpus/aeat_official/instructions/`,
  which are evidence captures and must not be hand-edited.

## Decision trail (5 superseded streams)

Five vault streams produced the architecture under audit. Each stream is to
be marked superseded by the upcoming `google-oauth` ADR; their indexes
(`.vault/google-auth-ux.index.md`,
`.vault/google-workspace-mcp-auth.index.md`,
`.vault/gsuite-bootstrap.index.md`) should be retired or repointed in
the curate pass that follows the excision.

### `gsuite-bootstrap` (2026-04-12)

Committed to using `gcloud auth application-default login` as the
canonical operator bootstrap and treated Application Default Credentials as
the primary local-dev credential surface. Live discovery (AUTH-005) found
that Google's own gcloud-built-in OAuth client cannot consent to Workspace
scopes (Drive/Sheets/Docs) at all; the stream then patched the recipes
with a `--client-id-file` workaround that re-injects an
operator-supplied Desktop OAuth client JSON. The architecture is wrong at
the foundation: the project does not need `gcloud`, ADC, or any GCP
plumbing to fetch and write Drive and Sheets documents - it needs a
self-hosted OAuth application and the standard user-facing consent flow.
Status: superseded.

### `google-fixtures` (2026-04-12)

Pure consumer of `gsuite-bootstrap`. Provisioned scratch Drive folder,
Sheet, and Doc fixtures for live tests via
`scripts/provision_google_fixtures.py` and a teardown counterpart. The
`scripts/` directory no longer exists on disk, but the justfile still
exposes `google-fixtures-provision` and `google-fixtures-teardown`
recipes that point at the deleted files (dead pointers, see below). The
fixture model itself remains valid for the new design but the bootstrap
path it relied on does not. Status: superseded.

### `google-workspace-mcp-auth` (2026-04-16)

Built `aeat.entrypoints.mcp.launch_google_workspace`, a thin shim that
wrapped a community MCP server with environment derived from the
`gsuite-bootstrap` ADC + service-account split. The Python module no
longer exists on disk, but `.mcp.json` still references it (dead
pointer, see below). Status: superseded; MCP integration is out of scope
for the `google-oauth` feature and will be reconsidered separately if
needed.

### `google-auth-ux` (2026-04-21)

Attempted to unify three diverging operator stories (Desktop OAuth
local-dev, Service-account automation, ADC) into one `aeat auth init` /
`aeat auth doctor` UX. Code review surfaced five critical defects; the
contract review surfaced five ADR gaps. The implementation never reached
green. The 40 KB `src/aeat/entrypoints/cli/auth/__init__.py` is the
surviving artifact of this stream. Status: superseded; the upcoming ADR
will replace `aeat auth init|doctor` for the Google side with a single
`aeat google login|status` pair plus a one-line `aeat google logout`
for token deletion.

### `restructure-google-split` (2026-05-01)

Pure relocation. Moved Google-specific symbols out of
`src/aeat/adapters/outbound/aeat/auth/` into
`src/aeat/adapters/outbound/google/` as part of the
`chore/eliminate-shims` restructure. No semantic change. The relocated
files are listed in the code surface ledger below. Status: superseded only
insofar as the contents are now slated for excision.

## Code surface ledger

### Adapter package - `src/aeat/adapters/outbound/google/`

- `__init__.py` (17.8 KB / 468 lines) - module docstring documenting the
  two operator-facing paths, scope constants (`DRIVE_SCOPE`,
  `SHEETS_SCOPE`, `DOCS_SCOPE`, `CLOUD_PLATFORM_SCOPE`,
  `USERINFO_EMAIL_SCOPE`, `OPENID_SCOPE`, `SCOPES`,
  `REQUIRED_ADC_SCOPES`, `ADC_LOGIN_SCOPES`,
  `ADC_LOGIN_SCOPE_CSV`, `DRIVE_READONLY_SCOPES`,
  `SHEETS_READONLY_SCOPES`, `DOCS_READONLY_SCOPES`,
  `DRIVE_FILE_SCOPES`, `STORAGE_FULL_CONTROL_SCOPE`,
  `STORAGE_READ_ONLY_SCOPE`), OAuth credentials acquisition
  (`get_oauth_credentials`, `get_credentials`,
  `get_credentials_for_scopes`, `get_adc_credentials_with_scopes`),
  service-account credentials (`get_service_account_credentials`),
  service builders (`build_drive_service`, `build_sheets_service`,
  `build_docs_service`, `build_serviceusage_service`,
  `build_storage_client`, `build_cloudfunctions_client`,
  `build_cloudrun_client`), and the scope-verification helper
  `assert_credentials_have_scopes`.
- `_paths.py` (20.4 KB / 489 lines) - `GoogleAuthPath` enum,
  `GoogleAuthInspection` dataclass, `inspect_google_auth` resolver,
  ADC well-known path resolution (`adc_well_known_path`), the
  Desktop-OAuth required-scope tuple (`DESKTOP_OAUTH_REQUIRED_SCOPES`),
  and the secure-object-backed token-cache helpers
  (`load_oauth_token_cache`, `save_oauth_token_cache`,
  `delete_oauth_token_cache`, `inspect_oauth_token_cache`, plus the
  parallel namespaces for OAuth client JSON and service-account JSON).
- `test_google.py` - adapter tests for the credential resolver, scope
  helpers, and service builders.
- `test_auth_helpers.py` - tests for `inspect_google_auth` precedence,
  inactive-path drift detection, and token-cache inspection.

### CLI entrypoints - `src/aeat/entrypoints/cli/`

- `auth/__init__.py` (40.4 KB) - the surviving `aeat auth init|doctor`
  surface from the `google-auth-ux` stream, importing `SCOPES`,
  `GoogleAuthPath`, `delete_oauth_token_cache`, `get_credentials`,
  `inspect_google_auth`, `save_google_oauth_client_json`,
  `save_google_service_account_json` from the adapter package.
- `auth/_render.py` - Rich rendering helpers for the auth diagnostics.
- `auth/_registry.py` - provider-registry table renderer; partly
  Google-flavoured.
- `auth/test_auth_cli.py` (24.9 KB) - CLI surface tests covering the
  Desktop OAuth + Service-account journeys.
- `auth/conftest.py` - fixtures for the auth CLI suite.
- `oauth.py` (~4 KB) - `aeat oauth-client` Typer sub-app that prints
  the Cloud Console credentials-page link and parses the downloaded OAuth
  client JSON into env settings.
- `_test_oauth.py` - tests for the OAuth client provisioning helper.
- `drive.py` (~9 KB) and `_drive_helpers.py` (~7 KB) - Drive CLI
  surface and helper layer.
- `_test_drive_helpers.py`, `_test_drive_live.py` - Drive helper unit
  and live tests.
- `docs.py` (~3.5 KB) and `_docs_helpers.py` (~4 KB) - Docs CLI
  surface and helper layer.
- `_test_docs_helpers.py`, `_test_docs_live.py` - Docs helper unit
  and live tests.
- `_sheets_helpers.py` (~2 KB) - Sheets helper layer (no top-level
  `sheets.py` CLI; helpers are consumed by bootstrap and live tests).
- `_test_sheets_helpers.py`, `_test_sheets_live.py` - Sheets helper
  unit and live tests.
- `cloud.py` (~7 KB) - Cloud Functions / Run / Storage CLI surface.
- `_test_cloud.py`, `_test_cloud_live.py` - Cloud product tests.
- `bootstrap.py` (~8.5 KB) - orchestrates fixture/scratch resource
  creation against the resolved Google credentials.
- `_test_bootstrap.py` - bootstrap CLI tests.
- `doctor.py` (~46 KB) - the diagnostic command; not entirely Google but
  a large fraction of its checks consult `inspect_google_auth` and report
  Desktop OAuth / Service-account readiness.
- `_test_doctor.py` (~21.6 KB) - doctor tests covering the Google checks.
- `_live.py` (~7 KB) - live-test gating helper used by every
  `_test_*_live` module.
- `_test_auth.py` (~5.8 KB) - additional auth-flavoured CLI tests at the
  CLI package root.

### Application setup - `src/aeat/application/setup/`

- `_models.py` - `FixtureProvisioningOpts`, `provision_google_fixtures`
  step model, `aeat_live_tests_google` flag plumbing.
- `_wizard.py` - interactive setup wizard that branches on Google auth
  path selection.
- `_env_writer.py` - writes Google env vars during setup.
- `_protocols.py` - typed protocols consumed by the setup wizard,
  including the Google fixture provisioner.
- Co-located `test_*.py` modules under the same directory exercise the
  above.

### Core - `src/aeat/core/config.py`

- `GoogleAuthPathSetting` `StrEnum` - settings-shape mirror of the
  adapter `GoogleAuthPath` enum.
- Google Settings fields (lines 104-151): `google_auth_path`,
  `google_oauth_client_id`, `google_oauth_client_secret`,
  `google_oauth_redirect_uri`, `google_oauth_client_json`,
  `google_application_credentials`, `google_impersonate_email`,
  `google_cloud_project`, `google_sheets_spreadsheet_id`,
  `google_drive_folder_id`, `google_cloud_storage_bucket` - 11
  fields.
- Test fixture fields (lines 242-250):
  `aeat_google_test_fixtures_folder_id`,
  `aeat_google_test_fixture_smoke_sheet_id`,
  `aeat_google_test_fixture_smoke_doc_id` - 3 fields.
- `aeat_live_tests_google` (around line 311) - secondary opt-in for
  Workspace fixture live tests.
- `field_validator` covering `google_oauth_client_json` and
  `google_application_credentials` (around line 810).

### Tests at `tests/`

- `tests/test_justfile_google_auth.py` - verifies the existence and shape
  of the `gsuite-*`, `gcloud-*`, and `google-fixtures-*` recipes.
- `tests/test_config.py` - coverage of the Google settings fields.
- `tests/test_release_config.py` - release-shape coverage that lists the
  Google fields.
- `tests/import_contract/test_adr_layout_import_smoke.py` - asserts that
  `aeat.adapters.outbound.google` is importable and exposes
  `GoogleAuthPath`, `get_credentials_for_scopes`, and
  `inspect_google_auth`. **This contract will fail the moment the
  adapter package is removed and must be updated atomically with the
  excision.**

## Config and manifest ledger

### `pyproject.toml`

Runtime dependencies under the `Google Cloud / Workspace` block (lines
33-42):

- `google-api-python-client>=2.194.0`
- `google-auth>=2.49.1`
- `google-auth-httplib2>=0.3.1`
- `google-auth-oauthlib>=1.3.1`
- `google-cloud-functions>=1.20.0`
- `google-cloud-run>=0.10.18`
- `google-cloud-storage>=3.10.1`
- `gspread>=6.2.1`

Eight runtime dependencies plus their transitives in `uv.lock`. The
`tool.ty.analysis.allowed-unresolved-imports` list (lines 263-268)
carries `gspread`, `googleapiclient`, `google.auth`,
`google.oauth2`, `google.cloud`, `google_auth_oauthlib`. The
pytest marker block describes `live_read` (covers Google scratch
round-trips) and a `domain_outbound` marker that enumerates `google`
among its targets.

### `env/.env.example`

Fourteen in-scope Google keys grouped under `-- Google Auth --` through
`-- Live tests --` (lines 1-173):

- `GOOGLE_AUTH_PATH`, `GOOGLE_OAUTH_CLIENT_ID`,
  `GOOGLE_OAUTH_CLIENT_SECRET`, `GOOGLE_OAUTH_REDIRECT_URI`,
  `GOOGLE_OAUTH_CLIENT_JSON`, `GOOGLE_APPLICATION_CREDENTIALS`,
  `GOOGLE_IMPERSONATE_EMAIL`, `GOOGLE_CLOUD_PROJECT`,
  `GOOGLE_SHEETS_SPREADSHEET_ID`, `GOOGLE_DRIVE_FOLDER_ID`,
  `GOOGLE_CLOUD_STORAGE_BUCKET`, `AEAT_GOOGLE_TEST_FIXTURES_FOLDER_ID`,
  `AEAT_GOOGLE_TEST_FIXTURE_SMOKE_SHEET_ID`,
  `AEAT_GOOGLE_TEST_FIXTURE_SMOKE_DOC_ID`, `AEAT_LIVE_TESTS_GOOGLE`.

The doc-comments around these keys still reference `just gcloud-auth`,
`just gsuite-oauth-client`, the `--client-id-file` workaround, and the
ADC-vs-service-account split - all of which become stale once the new
design lands.

### `justfile`

POSIX + Windows pair recipes (`gcloud-install`, `gcloud-setup`,
`gcloud-auth`, `gsuite-enable-apis`, `gsuite-enable-apis-billing`,
`gsuite-bootstrap`, `gsuite-bootstrap-sa`, `gsuite-doctor`,
`gsuite-oauth-client`, `google-fixtures-provision`,
`google-fixtures-teardown`) - eleven logical recipes, twenty-two recipe
bodies including the platform variants. The recipes shell out to `gcloud`,
read `GOOGLE_OAUTH_CLIENT_JSON` from `env/.env`, and invoke deleted
scripts (see dead pointers). The `aeat-cert-fetch` recipe also calls
`aeat drive fetch`, so removing the `drive` CLI breaks that recipe and
it needs a replacement or deletion decision.

### `.gitignore`

- `gcp-oauth.keys.json`
- `.gdrive-server-credentials.json`
- `.mcp-google-sheets-token.json`

Three Google-related ignore rules. All three become unnecessary under the
SQL-substrate token-storage model proposed in the research doc.

### `.mcp.json`

- The `google-workspace` server entry points at the deleted module
  `aeat.entrypoints.mcp.launch_google_workspace`. Dead pointer.

### `docs/conf.py`

- Intersphinx mappings for the Google libraries.
- `autodoc_mock_imports` entries: `google`, `googleapiclient`,
  `google_auth_oauthlib`.

## Locales

A case-insensitive `grep` for `google|drive|sheets|oauth|gcloud|gsuite|gcp`
against the quad-lingual locale files reports:

- `src/aeat/locales/en.yml` - 85 hit lines (out of 1267 total)
- `src/aeat/locales/es.yml` - 85 hit lines (out of 1302 total)
- `src/aeat/locales/ca.yml` - 85 hit lines (out of 1295 total)
- `src/aeat/locales/hu.yml` - 86 hit lines (out of 1302 total)

Approximately 340 user-facing strings across the four languages tied to the
discarded design (the bulk live under `cli.auth.*`, `cli.oauth.*`,
`cli.drive.*`, `cli.docs.*`, `cli.cloud.*`, `cli.bootstrap.*`,
`cli.doctor.*`, plus the setup-wizard prompts). Replacement strings for
the new `aeat google login|status|logout` surface will be much smaller.

## Docs

- `docs/api/aeat.adapters.outbound.google.rst` - generated API reference
  for the adapter.
- `docs/api/aeat.entrypoints.cli.{oauth,drive,docs,cloud,bootstrap,doctor}.rst`
  - six generated API references.
- `docs/_build/markdown/api/` - matching Markdown rebuilds for every
  page above.
- `README.md` - approximately 19 hit lines that document the operator
  bootstrap chain (gcloud install, gsuite-oauth-client, bootstrap,
  fixtures).
- `CONTRIBUTING.md` - approximately 13 hit lines covering live-test
  setup and Google fixture preconditions.

## Dead pointers already on disk

These are pre-existing breakages caused by partial rollback of earlier
streams. The excision plan should treat them as zero-cost cleanup
opportunities to fold into the same change.

- `.mcp.json` references `aeat.entrypoints.mcp.launch_google_workspace`
  - the module file does not exist; any MCP client that loads the manifest
  will fail to start the `google-workspace` server.
- `justfile` `google-fixtures-provision` invokes
  `scripts/provision_google_fixtures.py`; the `scripts/` directory does
  not exist in the worktree.
- `justfile` `google-fixtures-teardown` invokes
  `scripts/teardown_google_fixtures.py`; same condition.

## Quantification

- Adapter package: 4 files, ~957 lines of Python.
- CLI Google surface: ~22 production + test files in
  `src/aeat/entrypoints/cli/`, totalling several thousand lines (the
  largest single contributors are `auth/__init__.py` at ~40 KB,
  `doctor.py` at ~46 KB partially in scope, and
  `auth/test_auth_cli.py` at ~25 KB).
- Application setup: 4 production modules + co-located tests, 1
  fixture-provisioning step model.
- Core config: ~15 settings fields including the live-tests flag plus one
  validator and one settings-mirror enum.
- Tests at `tests/`: 4 modules including the import-contract that must be
  edited atomically with the adapter excision.
- Manifests: 8 runtime dependencies, ~14 env keys, 11 logical justfile
  recipes (22 recipe bodies), 3 `.gitignore` entries, 1 dead `.mcp.json`
  entry, 3 `docs/conf.py` entries.
- Locales: ~340 strings across four languages.
- Docs: 7 .rst pages, matching markdown rebuilds, ~32 hit lines across
  `README.md` + `CONTRIBUTING.md`.

## Recommendations

- Treat the upcoming `google-oauth` ADR as the single point of truth that
  marks all five decision-trail streams superseded; do not let any of them
  keep an "active" status into the new design.
- The excision pull request must update
  `tests/import_contract/test_adr_layout_import_smoke.py` in the same
  commit as the adapter removal; otherwise the import-contract guard will
  prevent the adapter from being deleted.
- Fold the three dead pointers (`.mcp.json` Google entry, two missing
  `scripts/` justfile recipes) into the same change - they are pure
  cleanup with no behavioural risk.
- The Gemini LLM provider
  (`src/aeat/adapters/outbound/llm/_providers/gemini.py`) is unrelated and
  must be left untouched; flag it explicitly in the plan to prevent
  accidental removal during dependency cleanup.
- Defer any MCP integration decision; remove the dead `.mcp.json` entry
  now and let any future MCP work originate from a fresh design pass.
