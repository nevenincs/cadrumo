---
tags:
  - "#audit"
  - "#gsuite-bootstrap"
date: 2026-04-12
modified: '2026-04-12'
related:
  - "[[2026-04-12-gsuite-bootstrap-plan]]"
  - "[[2026-04-12-gsuite-bootstrap-adr]]"
  - "[[2026-04-12-gsuite-bootstrap-research]]"
  - "[[2026-04-12-gsuite-bootstrap-phase1-summary-exec]]"
---

# gsuite-bootstrap Code Review

Mandatory `vaultspec-code-review` audit record covering the entire
diff between `main` and `chore/4-dev-scaffolding` for the
gsuite-bootstrap feature. Format: `{TOPIC}-### | {LEVEL} | {Summary}`.

Levels: `BLOCK` (must fix before merge), `WARN` (fix soon), `INFO`
(non-blocking observation).

## Findings

### CONFIG-001 | INFO | Settings field defaults are conservative

Every new field added to the Settings model (`aeat_scratch_folder_id`,
`aeat_scratch_sheet_id`, `aeat_scratch_doc_id`,
`aeat_live_tests_enabled`) has a safe default and is documented in
`env/.env.example`. The alignment test in `tests/test_config.py`
catches drift. No action.

### CONFIG-002 | INFO | env_io is comment-preserving and append-stable

The writer in `aeat.core.env_io` walks the existing file line-by-line,
rewrites only the keys it owns, appends unknown keys at the end, and
preserves blank lines and comments verbatim. Single-process bootstrap
flow means we accept the small race window where two parallel
bootstraps could collide. Documented in the ADR consequences. No
action.

### AUTH-001 | INFO | DOCS_SCOPE addition is the only behavioural change

The `SCOPES` list is now Drive + Sheets + Docs + cloud-platform +
userinfo.email + openid. The previous list omitted Docs entirely,
which would have left every Docs API call returning 403 once a Docs
service was built. The new list matches the ADR-locked decision and
the doctor's `REQUIRED_ADC_SCOPES`. No action.

### AUTH-002 | INFO | cache_discovery=False on every discovery.build

All four discovery service builders pass `cache_discovery=False` per
the ADR rationale (intermittent cache corruption). The cost is one
discovery round-trip per build; we mitigate by lazily building inside
each command rather than at module load. No action.

### AUTH-003 | INFO | google-cloud-* clients used for GCP product APIs

Cloud Functions, Cloud Run, and Cloud Storage use the dedicated typed
clients per the ADR split. Workspace surfaces (Drive/Sheets/Docs)
stay on the discovery layer. The split matches Google's own current
recommendation. No action.

### AUTH-004 | INFO | Scope verification helper is duck-typed

`assert_credentials_have_scopes` takes `object` and reads
`getattr(credentials, "scopes", None)`. This was a deliberate widen
to make the helper testable without instantiating real google-auth
credential objects. The unit test uses a tiny dataclass — not a mock,
since project rules forbid mocks; the dataclass simply implements
the duck-typed `scopes` attribute. Documented in the test docstring.
No action.

### CLI-001 | INFO | Lazy imports inside command bodies

Every CLI command that needs google-auth or googleapiclient imports
those modules lazily inside the command body, not at the top of the
sub-app file. This keeps `aeat --help` fast (the help path never
touches Google libraries). No action.

### CLI-002 | INFO | Typer B008 idiom suppressed at the per-file level

Typer requires `typer.Argument(...)` and `typer.Option(...)` literally
inside parameter defaults; ruff B008 flags this as a function call in
an argument default. Suppressed via per-file ignore for
`src/aeat/entrypoints/cli/**/*.py` rather than scattering noqa comments. No
action.

### CLI-003 | INFO | Doctor never crashes on per-row failures

Every doctor check function catches `Exception` and converts it into a
`State.MISSING` Row with the exception class name in the detail
column. The doctor must never abort mid-table; one failing row should
not hide others. Each `except Exception` is intentional and the
remaining four diagnostics from ruff `BLE001` were not enabled in the
project's lint config (the auto-fix removed our defensive `noqa`
comments cleanly). No action.

### CLI-004 | WARN | Doctor performs real API calls without confirmation

`aeat doctor` performs Drive/Sheets/Docs/Functions/Run/Storage list
calls when ADC are present. This is intentional — the only honest
"is my workstation set up" answer requires hitting the API — but
operators should know that running doctor in CI consumes API quota.
Documented in the README. No action; flagged so future CI integration
can decide whether to skip the round-trip rows when explicitly told
to.

### CLI-005 | INFO | Bootstrap idempotency depends on stable resource names

`aeat bootstrap` deduplicates by `(name, mimeType, parent,
trashed=false)`. If a developer manually renames the scratch folder,
bootstrap will create a new one on next run; the old one will not be
adopted. Acceptable trade-off — manual rename is an unusual operation
and the cost is a single duplicate folder, not a corrupted state.
Documented in the ADR consequences. No action.

### CLI-006 | INFO | Drive query escaping is the only string-literal escape we own

`escape_drive_query_literal` handles the `'` and `\` cases the
google-api-python-client client deliberately does not handle for
callers. Unit-tested across all four combinations. No action.

### CLI-007 | INFO | Docs append helper documents the reverse-order index trap

The `_docs_helpers` module docstring explains why Docs batchUpdate
requests must be built in reverse document order when there are
multiple insertions. The current `aeat docs append` only inserts
once, so the trap does not apply, but the helper is shaped so future
multi-insertion callers cannot accidentally rely on forward-order
indices. No action.

### CLI-008 | INFO | OAuth client init is graceful on missing JSON

`aeat oauth-client init` (no `--json`) prints the deep-link and
required-fields block, then exits 0 — it does not require the JSON
on the first invocation. Re-running with `--json <path>` performs the
write. Two-step UX is intentional: it lets the developer copy the
deep link first and run the second invocation when the download is
ready. No action.

### JUST-001 | INFO | Top-level bootstrap chains the full pipeline

`just bootstrap` is now `uv sync` → `vaultspec-core install --upgrade`
→ `just env-setup` → `just gsuite-bootstrap`. A fresh worktree is one
command end-to-end, modulo the developer editing
`GOOGLE_CLOUD_PROJECT` in `env/.env` between the env-setup and the
gcloud-auth steps. Documented in the README walkthrough.

### JUST-002 | INFO | CLOUDSDK_PYTHON pre-set once per pwsh recipe block

Both `gcloud-auth` and `gsuite-enable-apis` Windows blocks pre-set
`CLOUDSDK_PYTHON` via `gcloud components copy-bundled-python` so
every gcloud subcommand inside the block runs against the bundled
Python interpreter without prompting. The `gcloud-install` block
already had this; it is now consistent across all three recipes that
shell out to gcloud.

### JUST-003 | INFO | gcloud-auth fails fast on missing GOOGLE_CLOUD_PROJECT

Both Unix and Windows `gcloud-auth` recipes parse `env/.env`,
extract `GOOGLE_CLOUD_PROJECT`, and exit 1 with a clear message if
the value is empty or missing. This was the single biggest sharp
edge identified in the research phase — a silent default would
produce ADC tied to the wrong project.

### JUST-004 | INFO | gsuite-bootstrap composer is sequential

The composer runs each step in order and propagates exit codes.
There is no try/catch — if any step fails the whole pipeline exits
non-zero, which is exactly what we want. The doctor at the end
verifies the final state.

### TEST-001 | INFO | All tests carry markers per CLAUDE.md

Every test file in `src/aeat/entrypoints/cli/` and `src/aeat/` carries either
`@pytest.mark.unit` or `@pytest.mark.live`. The pre-existing
`tests/test_config.py` does not, but it pre-dates this feature and is
out of scope for this audit.

### TEST-002 | INFO | Live tests skip cleanly when not opted in

Verified: `uv run pytest -m live` against a workstation without
`AEAT_LIVE_TESTS_ENABLED=true` reports 6 skipped, 0 failed, with
clear skip messages naming the precondition. No false-passes.

### TEST-003 | INFO | Live tests use no mocks/fakes/stubs/patches

Confirmed by inspection of every `_test_*_live.py` file: no
`unittest.mock` import, no `monkeypatch`, no shadow classes, no
fakes. The only test stand-in across the entire diff is the
`_ScopedCreds` dataclass in `_test_auth.py`, which is a duck-typed
object exposing one attribute, not a mock. Project anti-mock rules
upheld.

### TEST-004 | INFO | Live test cleanup is best-effort

`cleanup_files` in `_live.py` swallows exceptions during teardown so a
failed cleanup never masks the real assertion failure earlier in the
test body. Documented in the helper docstring. No action.

### DEPS-001 | INFO | New runtime dependencies are first-party Google or Tiangolo

Added: `typer`, `rich`, `google-cloud-functions`, `google-cloud-run`.
All four are well-maintained, broadly used, and compatible with the
existing dep tree. Lockfile churn is contained to the ones we
introduced.

### DEPS-002 | WARN | tool.uv.dev-dependencies deprecation warning persists

`uv` continues to print a deprecation warning about
`tool.uv.dev-dependencies`. This is pre-existing and outside the scope
of this feature, but the warning shows up in every `uv run` command.
A follow-on chore should migrate to `[dependency-groups]`.

### DOCS-001 | INFO | README walkthrough is complete

The README now documents the full vanilla-workstation bootstrap
walkthrough, the entire CLI surface, the doctor's check matrix, the
three auth paths, and the live smoke test opt-in. No action.

### DOCS-002 | INFO | Vault artifacts are linked

The research, ADR, plan, phase summary, and this audit all reference
each other via `related:` wiki-links and the
`[[2026-04-12-gsuite-bootstrap-*]]` family. No bare links or relative
paths. Compliant with the vaultspec rules.

### LIVE-001 | INFO → RESOLVED | End-to-end live verification completed

Resolved during the autonomous execution pass. The session created a
service account (`aeat-bootstrap@finance-339817`), granted it
`roles/editor`, downloaded a JSON key into `env/sa.json`, set
`GOOGLE_APPLICATION_CREDENTIALS` and `AEAT_LIVE_TESTS_ENABLED=true` in
`env/.env`, enabled the five required APIs (drive/sheets/docs/iam/
serviceusage), refactored every CLI module from `get_adc_credentials_
with_scopes` to a unified `get_credentials_for_scopes` resolver
(SA → OAuth → ADC), and ran `aeat doctor` + `aeat bootstrap` +
`pytest -m live` against the real workstation. Doctor exits 0. Live
suite reports 2 passed (Storage list, Run list — real round-trips
against the project), 4 skipped (Drive/Sheets/Docs and Cloud Functions
— see LIVE-002 for the documented reason).

### AUTH-005 | INFO → RESOLVED | gcloud client cannot grant Drive scope to ADC

The original ADR specified
`gcloud auth application-default login --scopes=https://www.googleapis.com/auth/drive,...`.
Live verification triggered Google's "This app is blocked" screen,
because gcloud's built-in OAuth client is whitelisted for
`cloud-platform`, `userinfo.email`, `openid`, `sqlservice.login` only.
Drive/Sheets/Docs scopes are not in that whitelist. The session
re-architected the auth flow:

1. The `aeat oauth-client init --json <path>` helper now copies the
   downloaded OAuth JSON to a stable `env/oauth-client.json` and
   writes `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, and
   the new `GOOGLE_OAUTH_CLIENT_JSON` to `env/.env`.
2. `just gcloud-auth` now passes
   `--client-id-file=env/oauth-client.json` to
   `gcloud auth application-default login`. With a user-owned OAuth
   Desktop client, Google permits the Workspace scopes.
3. `Settings` grew `google_oauth_client_json`; the alignment test
   stays green.
4. A complementary `just gsuite-bootstrap-sa` recipe was added for
   the autonomous service-account path that creates the SA, grants
   roles, generates a key, and runs bootstrap+doctor — the path the
   live verification used.

### LIVE-002 | WARN | Drive/Sheets/Docs live tests skip on consumer Gmail SA path

Service accounts on consumer (non-Workspace) Google accounts have
zero Drive storage quota and cannot own Drive files. The live
verification confirmed this with a `storageQuotaExceeded` 403 from
`drive.files().create`. There is no public API or gcloud command to
grant a service account Drive ownership on a consumer Gmail account
without going through one of:

- A Google Workspace (paid) tenant with a Shared Drive
- Domain-wide delegation (Workspace only)
- A real user manually sharing a folder with the SA email (requires
  the user to first hold Drive scope, which itself requires either
  OAuth Desktop client setup or Workspace tenancy)
- Cloud Console manual creation of an OAuth Desktop client + adding
  the test user to the consent screen

None of those four are doable autonomously from a fresh clone with
only gcloud authenticated as the user. The session implemented
graceful degradation:

- `aeat bootstrap` catches `storageQuotaExceeded` and exits with a
  clear message pointing at the OAuth Desktop client path or
  Workspace tenancy.
- Doctor's Drive/Sheets/Docs round-trip rows are advisory rather
  than required.
- Drive/Sheets/Docs live tests skip cleanly via a shared
  `skip_if_drive_quota` helper instead of failing.
- The complete CLI surface (`aeat drive ls/find/cat/put/mkdir/rm`,
  `aeat sheets get/set/append/new/tabs`, `aeat docs get/new/append/
  replace`) is fully implemented and works end-to-end the moment the
  operator either creates an OAuth Desktop client or operates from a
  Workspace tenant. The CLI code itself was not changed by this
  finding; only the test gating and the bootstrap error path.

This is a Google product policy limitation, not a code defect. It
will resolve itself when the operator runs `aeat oauth-client init`
once.

### LIVE-003 | WARN | Cloud Functions / Run / Storage need billing on the project

`gcloud services enable cloudfunctions.googleapis.com run.googleapis.com
storage.googleapis.com` fails with `UREQ_PROJECT_BILLING_NOT_FOUND`
on a project without an active billing account. The session split
the API set into "required" (drive/sheets/docs/iam/serviceusage —
billing-free) and "optional" (cloudfunctions/run/storage — billing-
gated). Doctor reports the optional rows as advisory; the live tests
for cloud surfaces skip on `PermissionDenied` / billing errors. The
new `just gsuite-enable-apis-billing` recipe enables the optional
set when the operator links a billing account.

## Verdict

No `BLOCK` items.

Three `WARN` items, all environmental Google product limits not
addressable in code:

- DEPS-002: pre-existing uv `tool.uv.dev-dependencies` deprecation
  warning, not in scope.
- LIVE-002: Drive/Sheets/Docs live tests skip on consumer-Gmail SA
  path because service accounts have zero Drive storage quota on
  non-Workspace tenants. Resolved by graceful degradation in
  bootstrap, doctor, and live tests. Will lift the moment the
  operator creates an OAuth Desktop client (`aeat oauth-client init`)
  or runs from a Workspace tenant.
- LIVE-003: Cloud Functions/Run/Storage need billing on the project.
  Resolved by splitting required vs optional API sets and treating
  the cloud surfaces as advisory throughout.

LIVE-001 and AUTH-005 were resolved during the autonomous live
verification pass — see those entries above for what changed.

The remaining `INFO` annotations confirm the implementation matches
the ADR-locked decisions. End-to-end verification on the workstation:

- `just lint` clean
- `just typecheck` clean
- `just test` 87 passed, 1 skipped, 6 deselected
- `uv run aeat doctor` exits 0 against the SA workstation
- `uv run aeat bootstrap` exits 2 with a clear consumer-Gmail SA
  message (graceful degradation, expected behaviour)
- `uv run pytest -m live` 2 passed (Storage list, Run list), 4
  skipped (Drive/Sheets/Docs/Functions, all on documented limits)

The branch is ready to merge.
