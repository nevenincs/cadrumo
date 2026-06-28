---
tags:
  - "#exec"
  - "#gsuite-bootstrap"
date: 2026-04-12
modified: '2026-04-12'
related:
  - "[[2026-04-12-gsuite-bootstrap-plan]]"
  - "[[2026-04-12-gsuite-bootstrap-adr]]"
  - "[[2026-04-12-gsuite-bootstrap-research]]"
---

# gsuite-bootstrap phase-1 summary

End-to-end execution of the gsuite-bootstrap plan on
`chore/4-dev-scaffolding`. All ten phases delivered, all audit
checkpoints green at the unit-test layer, live tests scaffolded and
opt-in via `just test-live`.

## Phases delivered

- **phase-1 — config + env-io substrate**: extended Settings with
  `aeat_scratch_folder_id`, `aeat_scratch_sheet_id`,
  `aeat_scratch_doc_id`, `aeat_live_tests_enabled`. Added
  `env/.env.example` placeholders and a comment-preserving
  `aeat.core.env_io` writer with full unit coverage. Configured pytest
  markers and the default `not live` filter.
- **phase-2 — auth module extensions**: added `DOCS_SCOPE`,
  `USERINFO_EMAIL_SCOPE`, `OPENID_SCOPE`, `STORAGE_FULL_CONTROL_SCOPE`;
  rewired `SCOPES` to cover Workspace + identity + cloud-platform;
  added `build_docs_service`, `build_serviceusage_service`,
  `build_storage_client`, `build_cloudfunctions_client`,
  `build_cloudrun_client`, `assert_credentials_have_scopes`,
  `get_adc_credentials_with_scopes`. Hoisted `REQUIRED_ADC_SCOPES`
  here so doctor and bootstrap share one source.
- **phase-3 — dependency wiring + CLI skeleton**: added typer, rich,
  google-cloud-functions, google-cloud-run as runtime dependencies;
  registered the `aeat` entry point in pyproject; laid down the
  per-surface sub-app skeleton with placeholder stubs.
- **phase-4 — doctor command**: full read-only health check with rich
  table output. Covers env file, GOOGLE_CLOUD_PROJECT, gcloud binary
  + auth + project, ADC file + scopes, API enablement via Service
  Usage, per-surface live round-trips for Drive/Sheets/Docs/Cloud
  Functions/Run/Storage, advisory rows for SA/OAuth Desktop, and the
  live-test opt-in flag. Pure helpers (`adc_well_known_path`,
  `adc_scopes_from_file`, `short_scope`, `render_table`) under
  colocated unit tests. Verified live: detected exactly the three real
  failures on the workstation (project empty in env, ADC scopes
  missing, refresh token expired).
- **phase-5 — bootstrap command**: idempotent name-based scratch
  resource creator. Locates or creates `aeat-scratch` Drive folder
  under My Drive root, then `aeat-scratch-sheet` and
  `aeat-scratch-doc` inside it, then writes the three IDs back into
  `env/.env` via `env_io.write_env_vars`. Pure `dedup_existing_resource`
  helper unit-tested across happy path, no-match, mime-mismatch,
  multi-match, empty listing.
- **phase-6 — Drive / Sheets / Docs CLI surfaces**: full verbs per the
  ADR. Drive: ls / find / cat (download or export) / put (resumable
  upload) / mkdir / rm (trash or permanent). Sheets: get / set / append
  / new / tabs. Docs: get (json or plaintext) / new / append /
  replaceAllText. Pure helpers in private `_drive_helpers`,
  `_sheets_helpers`, `_docs_helpers` modules with full unit coverage.
  Added `B008` per-file ignore for `src/aeat/entrypoints/cli/` so Typer's
  documented function-call-in-default idiom is allowed.
- **phase-7 — Cloud Functions / Run / Storage CLI**: list +
  describe verbs across the three product surfaces using the dedicated
  google-cloud-* clients. Lazy client construction so the `cloud`
  sub-app does not pay client load cost on `aeat --help`. Sub-app
  command-tree shape verified by colocated unit tests via
  `typer.testing.CliRunner`.
- **phase-8 — OAuth Desktop helper + justfile rewrite**: shipped
  `aeat oauth-client init` with the deep-link Cloud Console URL,
  required-fields block, and JSON parser that writes
  `GOOGLE_OAUTH_CLIENT_ID` / `GOOGLE_OAUTH_CLIENT_SECRET` into
  `env/.env`. Pure `parse_oauth_client_json` unit-tested across both
  installed/web shapes plus every error branch. Rewrote the justfile
  with `gcloud-install` (renamed from `gcloud-setup`, alias kept for
  back-compat), `gcloud-auth` (browser flows + scope set + project
  set, `CLOUDSDK_PYTHON` pre-set on Windows), `gsuite-enable-apis`
  (eight services), `gsuite-bootstrap` (the composer),
  `gsuite-doctor`, `gsuite-oauth-client`, `test-live`. The top-level
  `bootstrap` recipe now chains uv sync → vaultspec install →
  env-setup → gsuite-bootstrap so a fresh worktree is one command.
- **phase-9 — live smoke tests**: per-surface `@pytest.mark.live`
  tests in `_test_drive_live`, `_test_sheets_live`, `_test_docs_live`,
  `_test_cloud_live`. Shared `_live` fixtures + skip helpers + lazy
  service factories. Each test uses a UUID prefix and cleans up in a
  try/finally. Default `pytest` skips them via the
  `addopts = -m 'not live'` configuration; `just test-live` opts in.
  No mocks, fakes, stubs, or patches anywhere in the live tests.
- **phase-10 — README walkthrough**: complete rewrite of README.md
  covering vanilla-workstation bootstrap walkthrough, the full CLI
  surface, doctor semantics, ADC/OAuth/Service Account paths, live
  smoke test opt-in.

## Verification status

- `just lint` — clean (ruff)
- `just typecheck` — clean (ty)
- `just test` — 87 passed, 1 skipped, 6 deselected (live tests
  correctly excluded by default `-m 'not live'`)
- `just test -m live` (without opt-in) — 6 skipped cleanly with the
  documented "AEAT_LIVE_TESTS_ENABLED is false" message
- `uv run aeat --help` — lists every sub-app from the ADR
- `uv run aeat doctor` — renders the table truthfully against the
  real workstation; correctly flags GOOGLE_CLOUD_PROJECT empty, ADC
  scopes missing, and Drive round-trip RefreshError; exits non-zero
- `uv run aeat bootstrap` — not yet exercised end-to-end; requires
  the operator to first run `just gcloud-auth` to acquire ADC with the
  full scope set. Documented in the README and in the doctor's
  remediation hints.
- `just test-live` against a fully-bootstrapped workstation — not
  exercised in this execution session, deferred to the next live
  pass with the operator. The live tests are wired and skip cleanly;
  exhaustive live verification is the next session's first task.

## Outstanding work for the next session

The plan committed to "nothing deferred". Two items remain that the
execution session could not complete autonomously because they
require an interactive browser auth flow and an existing GCP project:

1. **`just gsuite-bootstrap` end-to-end run** — needs the developer
   (or operator) to click through the two browser flows in
   `gcloud auth login` and `gcloud auth application-default login`,
   confirm the scope set, and let the `aeat bootstrap` step create
   the scratch resources.
2. **`just test-live` green run** — depends on (1) above. Once the
   scratch IDs land in `env/.env` and `AEAT_LIVE_TESTS_ENABLED=true`
   is set, the Phase 9 suite can be exercised.

The session deliberately stopped short of forcing a browser flow on
the workstation without the operator's involvement, even in
autonomous mode. The plan is shaped so this final verification pass
is one command after the operator authorises the browser flows.

## Next steps

Proceed to the mandatory `vaultspec-code-review` audit, then open the
pull request.
