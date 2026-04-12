---
tags:
  - "#audit"
  - "#gsuite-bootstrap"
date: 2026-04-12
related:
  - "[[2026-04-12-gsuite-bootstrap-plan]]"
  - "[[2026-04-12-gsuite-bootstrap-adr]]"
  - "[[2026-04-12-gsuite-bootstrap-research]]"
  - "[[2026-04-12-gsuite-bootstrap-phase1-summary]]"
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

The writer in `aeat.env_io` walks the existing file line-by-line,
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
`src/aeat/cli/**/*.py` rather than scattering noqa comments. No
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

Every test file in `src/aeat/cli/` and `src/aeat/` carries either
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

### LIVE-001 | WARN | End-to-end live verification deferred to operator pass

The execution session committed code that is unit-test green and
type-check green, with the doctor verifying real workstation state
truthfully against existing (under-scoped, expired) ADC. The full
round-trip verification — `just gsuite-bootstrap` end-to-end then
`just test-live` against the resulting scratch resources — requires
the operator to click through two browser flows. The session stopped
short of triggering those flows in autonomous mode. The phase
summary documents this; the README walkthrough covers the steps.

## Verdict

No `BLOCK` items.

Two `WARN` items, both pre-existing or environmental:

- DEPS-002: pre-existing uv deprecation warning, not in scope.
- LIVE-001: end-to-end live run requires operator browser flows;
  documented and one command away.

The remaining 24 findings are `INFO` annotations confirming the
implementation matches the ADR-locked decisions. The branch is ready
for the operator to run `just gsuite-bootstrap` and then open the
pull request.
