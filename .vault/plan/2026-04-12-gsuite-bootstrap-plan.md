---
tags:
  - "#plan"
  - "#gsuite-bootstrap"
date: 2026-04-12
modified: '2026-04-12'
related:
  - "[[2026-04-12-gsuite-bootstrap-adr]]"
  - "[[2026-04-12-gsuite-bootstrap-research]]"
  - "[[2026-04-12-dev-scaffolding-plan]]"
---

# gsuite-bootstrap phase-1 plan

End-to-end implementation of the vanilla-workstation Google Workspace
bootstrap, the `aeat` CLI surface, the doctor health check, the
justfile recipe wiring, the live smoke tests, and the rolling audits.
Grounded in the accepted ADR and the research findings.

## Proposed Changes

Land the full feature on `chore/4-dev-scaffolding`. Nothing deferred.
Every phase block ends with an audit checkpoint that runs unit tests,
lint, type check, and (where the prerequisite credentials exist) live
smoke tests. The execution phase persists one exec record per task and
one phase summary per phase block. The final code review record gates
the merge conversation.

## Tasks

- **Phase 1 — config and env-io substrate**
  1. Extend `Settings` in `src/aeat/config.py` with
     `aeat_scratch_folder_id`, `aeat_scratch_sheet_id`,
     `aeat_scratch_doc_id`, `aeat_live_tests_enabled` (bool, default
     False). All have safe defaults.
  2. Append documented placeholders for the four new vars to
     `env/.env.example`. Confirm `tests/test_config.py` alignment test
     stays green.
  3. Add `src/aeat/env_io.py` — pure-python KEY=VALUE writer that
     preserves comments and ordering, with `read_env_file(path)`,
     `write_env_var(path, key, value)`, `write_env_vars(path, mapping)`.
     Co-located unit tests `src/aeat/_test_env_io.py` carrying
     `@pytest.mark.unit`.
  4. Update `pyproject.toml` `[tool.pytest.ini_options]` with the
     `markers` table and `addopts = "-v --tb=short -m 'not live'"`.
  5. Phase 1 audit: `just lint`, `just typecheck`, `just test`. All
     must be green.

- **Phase 2 — auth module extensions**
  1. In `src/aeat/auth.py`, add `DOCS_SCOPE`,
     `STORAGE_FULL_CONTROL_SCOPE`. Update `SCOPES` to include the
     `documents` scope. Re-export the narrower constants for
     least-privilege use.
  2. Add `build_docs_service`, `build_serviceusage_service`,
     `build_storage_client`, `build_cloudfunctions_client`,
     `build_cloudrun_client`. Workspace builders use
     `discovery.build(..., cache_discovery=False)`. Cloud builders use
     the dedicated `google-cloud-*` clients.
  3. Add `assert_credentials_have_scopes(creds, required)` helper that
     reads `creds.scopes` (or the ADC JSON for ADC creds) and verifies
     the required set is a subset.
  4. Add lazy `get_adc_credentials_with_scopes(scopes)` that wraps
     `google.auth.default(scopes=scopes)` and re-raises with a clearer
     message if ADC is missing or under-scoped.
  5. Co-located unit tests `src/aeat/_test_auth.py` for the pure helpers
     (`assert_credentials_have_scopes`, scope constant content) under
     `@pytest.mark.unit`. Network-touching code stays untested at unit
     level — covered by Phase 8 live tests.
  6. Phase 2 audit: `just lint`, `just typecheck`, `just test`.

- **Phase 3 — dependency wiring and CLI skeleton**
  1. Add `typer`, `rich`, `google-cloud-functions`, `google-cloud-run`,
     `google-cloud-storage` to `[project] dependencies` in
     `pyproject.toml`. Run `uv lock` and commit the lockfile churn.
  2. Add `[project.scripts] aeat = "aeat.entrypoints.cli.__main__:app"`.
  3. Create `src/aeat/entrypoints/cli/__init__.py` and
     `src/aeat/entrypoints/cli/__main__.py` with a `Typer` app that wires
     placeholder sub-apps for `doctor`, `bootstrap`, `drive`, `sheets`,
     `docs`, `cloud`, `oauth`. Each sub-app initially exposes one stub
     command that prints "not yet implemented" and exits 1, so the
     surface is shaped before any real work lands.
  4. `uv run aeat --help` must exit 0 and list every sub-app.
  5. Phase 3 audit: `just lint`, `just typecheck`, `just test`,
     `uv run aeat --help`.

- **Phase 4 — doctor command**
  1. Implement `src/aeat/entrypoints/cli/doctor.py` against the doctor decision
     matrix in the ADR. Use `rich.table.Table` for output. Each row
     records `section`, `required` (bool), `state` (`OK | MISSING |
     WARN | SKIP`), and `detail` (one-line remediation hint).
  2. Cover the env file, `GOOGLE_CLOUD_PROJECT`, gcloud binary +
     version, gcloud active account, gcloud project match, ADC file +
     scopes, scratch resources presence, API enablement via Service
     Usage, per-surface round-trip checks, advisory rows for SA/OAuth.
  3. Exit non-zero on any required `MISSING`.
  4. Co-located unit tests `src/aeat/entrypoints/cli/_test_doctor.py` covering the
     pure helpers (env file checking, scope subset checking) under
     `@pytest.mark.unit`. Real auth + API checks are exercised by the
     doctor itself in Phase 9.
  5. Phase 4 audit: `just lint`, `just typecheck`, `just test`,
     manual `uv run aeat doctor` invocation against the live workstation
     to confirm the table renders and current state is reported truthfully.

- **Phase 5 — bootstrap command**
  1. Implement `src/aeat/entrypoints/cli/bootstrap.py`:
     - Validate ADC presence and scope set; fail with a clear message
       if missing.
     - Validate API enablement target set; fail with a clear message if
       missing.
     - Locate or create the scratch Drive folder (`aeat-scratch`),
       scratch Sheet (`aeat-scratch-sheet`), scratch Doc
       (`aeat-scratch-doc`). All by name search inside the user's My
       Drive root with `trashed=false` and the appropriate
       `mimeType=application/vnd.google-apps.{folder,spreadsheet,document}`.
     - Persist their IDs to `env/.env` via `env_io.write_env_vars`.
     - Print a final summary table.
  2. Co-located unit tests `src/aeat/entrypoints/cli/_test_bootstrap.py` covering
     pure decision logic (e.g. `dedup_existing_resource(name, mime,
     listing)`), under `@pytest.mark.unit`. Anything that touches Google
     APIs is exercised by Phase 9 live tests.
  3. Phase 5 audit: `just lint`, `just typecheck`, `just test`, real
     `uv run aeat bootstrap` against live credentials.

- **Phase 6 — Drive / Sheets / Docs CLI surfaces**
  1. `src/aeat/entrypoints/cli/drive.py`:
     - `aeat drive ls [--folder ID]` — list with `name, id, mimeType,
       size, modifiedTime`.
     - `aeat drive find QUERY` — pass through Drive `q=` syntax.
     - `aeat drive cat FILE_ID [--export-mime MIME]` — download or
       export to stdout.
     - `aeat drive put LOCAL [--folder ID] [--name N] [--mime MIME]`
       — resumable upload.
     - `aeat drive mkdir NAME [--parent ID]`.
     - `aeat drive rm FILE_ID [--permanent]` — trash by default,
       `--permanent` calls `delete`.
  2. `src/aeat/entrypoints/cli/sheets.py`:
     - `aeat sheets get SPREADSHEET RANGE`.
     - `aeat sheets set SPREADSHEET RANGE VALUES_JSON [--raw]`.
     - `aeat sheets append SPREADSHEET RANGE VALUES_JSON`.
     - `aeat sheets new TITLE` — creates a new sheet, prints ID.
     - `aeat sheets tabs SPREADSHEET` — list tab titles.
  3. `src/aeat/entrypoints/cli/docs.py`:
     - `aeat docs get DOC_ID [--plaintext]`.
     - `aeat docs new TITLE`.
     - `aeat docs append DOC_ID TEXT` — uses the reverse-document-order
       helper.
     - `aeat docs replace DOC_ID OLD NEW` — find/replace via
       batchUpdate.
  4. Helper modules:
     - `src/aeat/entrypoints/cli/_drive_helpers.py` — query escaping, mime detection,
       resumable upload wrapper.
     - `src/aeat/entrypoints/cli/_sheets_helpers.py` — A1 range parsing, JSON value
       coercion.
     - `src/aeat/entrypoints/cli/_docs_helpers.py` — reverse-order batch builder
       helper.
  5. Co-located unit tests for every helper (`_test_drive_helpers.py`,
     `_test_sheets_helpers.py`, `_test_docs_helpers.py`) under
     `@pytest.mark.unit`. The CLI commands themselves are tested via
     the Phase 9 live tests; we deliberately do not write unit tests
     that mock googleapiclient (project rules forbid mocks).
  6. Phase 6 audit: `just lint`, `just typecheck`, `just test`.

- **Phase 7 — Cloud Functions / Run / Storage CLI**
  1. `src/aeat/entrypoints/cli/cloud.py`:
     - `aeat cloud functions list [--region REGION]`.
     - `aeat cloud functions describe NAME`.
     - `aeat cloud run list [--region REGION]`.
     - `aeat cloud run describe SERVICE`.
     - `aeat cloud storage buckets`.
     - `aeat cloud storage ls BUCKET [--prefix P]`.
  2. Each command builds the dedicated `google-cloud-*` client lazily.
  3. Co-located unit tests cover argument parsing only
     (`_test_cloud.py` with pure-typer testing using `CliRunner` against
     a stub callback), under `@pytest.mark.unit`.
  4. Phase 7 audit: `just lint`, `just typecheck`, `just test`.

- **Phase 8 — OAuth Desktop helper and justfile rewiring**
  1. Implement `src/aeat/entrypoints/cli/oauth.py` — `aeat oauth-client init`:
     - Print the deep-link Console URL for the active project's
       credentials page.
     - Print the required redirect URI and scope set.
     - Prompt for the path to the downloaded JSON.
     - Parse, extract `client_id` and `client_secret`, write into
       `env/.env`. Validate the JSON shape; fail loudly on bad input.
  2. Rewrite `justfile`:
     - Rename `gcloud-setup` → `gcloud-install`. Add a deprecation alias
       `gcloud-setup` that calls `gcloud-install` so existing muscle
       memory still works.
     - Add `gcloud-auth` per ADR — runs `gcloud auth login`,
       `gcloud config set project` (reads `GOOGLE_CLOUD_PROJECT` from
       `env/.env`), then `gcloud auth application-default login` with
       the locked Drive/Sheets/Docs/cloud-platform/userinfo.email
       scopes. Pre-sets `CLOUDSDK_PYTHON` once on Windows.
     - Add `gsuite-enable-apis` — runs the locked
       `gcloud services enable ...` list.
     - Add `gsuite-bootstrap` — composes
       `gcloud-install` → `gcloud-auth` → `gsuite-enable-apis` →
       `uv run aeat bootstrap` → `uv run aeat doctor`.
     - Add `gsuite-doctor` shortcut.
     - Add `gsuite-oauth-client` shortcut.
     - Add `test-live` recipe.
     - Update `bootstrap` so its final line invokes `gsuite-bootstrap`,
       making `just bootstrap` the single command for fresh worktrees.
  3. Phase 8 audit: `just lint`, `just typecheck`, `just test`,
     `just gsuite-doctor`, `just gsuite-bootstrap` against live
     credentials.

- **Phase 9 — live smoke tests**
  1. `src/aeat/entrypoints/cli/_live.py` — shared fixtures: `scratch_folder_id`,
     `scratch_sheet_id`, `scratch_doc_id`, `unique_prefix`, plus a
     `requires_live` skip decorator that checks
     `Settings.aeat_live_tests_enabled` and the relevant scratch ID.
  2. `src/aeat/entrypoints/cli/_test_drive_live.py`:
     - Create temp file with UUID prefix, list, fetch metadata, download
       content, delete. Assert content matches.
  3. `src/aeat/entrypoints/cli/_test_sheets_live.py`:
     - Set range, append, get, clear. Assert round-trip equality.
  4. `src/aeat/entrypoints/cli/_test_docs_live.py`:
     - Append text, get, verify presence, delete inserted range.
  5. `src/aeat/entrypoints/cli/_test_cloud_live.py`:
     - List Cloud Functions, list Cloud Run services, list Storage
       buckets. Each call must succeed (empty list is success).
  6. Phase 9 audit: `just test` (default skip-live, must stay green),
     then `just test-live` against the workstation. Both green.

- **Phase 10 — README walkthrough and final review**
  1. README section: vanilla-workstation bootstrap walkthrough — clone,
     `just bootstrap`, walk through both browser flows, run
     `just gsuite-doctor`, run `just test-live`.
  2. README section: CLI cheat sheet for every `aeat` subcommand,
     auto-generated from `aeat --help` output where reasonable.
  3. Phase 10 audit: `vaultspec-code-review` skill on the entire
     diff against `main`, persists
     `.vault/exec/2026-04-12-gsuite-bootstrap/2026-04-12-gsuite-bootstrap-review.md`.
     Address every required-fix item before declaring complete.

## Parallelization

The phases above are written in dependency order, but several can be
parallelized inside a single execution session:

- Phase 1 (config) and Phase 3 (dependency wiring + CLI skeleton) are
  independent and can land in parallel commits.
- Phase 6 sub-modules (`drive.py`, `sheets.py`, `docs.py`) and their
  helper unit tests are independent of each other and can be developed
  in parallel — they only share the `auth.py` builders from Phase 2.
- Phase 7 (`cloud.py`) is independent of Phase 6.
- Phase 9 live tests cannot start until Phases 5 (bootstrap creates
  scratch IDs) and 6 (CLI surfaces work) are both complete.
- Phase 10 review cannot start until everything else is committed.

Practical execution: the executor agent works through the phases
sequentially per the ADR, but commits each phase as a focused unit so
the audit checkpoints are inspectable.

## Verification

Mission success criteria, in order of strictness:

1. **Unit tests green**: `just test` exits 0. Every new module has
   colocated `_test_*.py` files under `@pytest.mark.unit`.
2. **Lint and type check green**: `just lint` and `just typecheck` exit
   0 with no warnings.
3. **CLI surface complete**: `uv run aeat --help` lists every sub-app
   from the ADR. Every sub-app's `--help` lists every command from
   Phase 6/7/8.
4. **Doctor pre-bootstrap**: `uv run aeat doctor` on a workstation
   without ADC reports the missing rows clearly and exits non-zero.
5. **Bootstrap end-to-end**: `just gsuite-bootstrap` on a workstation
   with the gcloud CLI installed completes both browser flows, enables
   the API set, creates the scratch resources, persists their IDs,
   and `aeat doctor` exits 0 afterwards.
6. **Live smoke tests green**: `just test-live` exits 0 against the
   scratch resources, exercising Drive, Sheets, Docs, and Cloud
   list-only round-trips with no mocks anywhere.
7. **Re-run idempotency**: running `just gsuite-bootstrap` a second
   time is a no-op on the API side and only re-writes the same env
   values. Doctor stays green.
8. **Hand-rolled smoke**: a human-style walkthrough — `aeat drive ls`,
   `aeat drive put` with a real local file, `aeat drive cat` of the
   uploaded file matching original bytes, `aeat sheets set` followed by
   `aeat sheets get` with matching values, `aeat docs append` followed
   by `aeat docs get --plaintext` showing the appended text, `aeat
   cloud storage buckets` returning whatever the project actually has
   (or an empty list cleanly).
9. **Code review record**: `vaultspec-code-review` exec record persisted
   under `.vault/exec/2026-04-12-gsuite-bootstrap/`. All required-fix
   items addressed before declaring done.
10. **Doctor as gating step**: `uv run aeat doctor` exits 0 in CI given
    a workstation with ADC and the API set enabled. This becomes the
    contract for any future CI integration without requiring the
    bootstrap recipe to run there.

Honest caveats:

- Tests can be cheated. The unit tests cover pure helpers; the live
  tests are the only real proof we hit Google APIs successfully. The
  hand-rolled smoke walkthrough in step 8 is the human-eyes layer that
  catches anything the live tests miss.
- The cloud surfaces (Functions/Run/Storage) are list-only in this
  feature. Deploy is explicitly out of scope and revisited in a follow-on
  feature, but this is documented in the ADR consequences and the
  README so it is not a silent omission.
- DWD impersonation paths are not exercised by live tests because they
  require a Workspace tenant the workstation may not have. Doctor reports
  the gate; the test suite skips it cleanly.
