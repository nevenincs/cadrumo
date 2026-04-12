# scripts/ — one-shot developer tooling

This directory is the project's documented escape hatch for Python that
is deliberately **not** shipped as part of the `aeat` library. Nothing
under `scripts/` is importable from runtime code; every file here is a
standalone entry point intended to be run directly (via
`uv run python scripts/<file>.py`) or through a `just` recipe.

The broader project layout rule still stands — application code lives
under `src/aeat/`. If you are tempted to put helpers here because they
feel "too small" for a subpackage, put them in the appropriate
subpackage instead. `scripts/` is for tooling that has no business
being on the import path.

## Current contents

| File                            | Role                                                     |
| ------------------------------- | -------------------------------------------------------- |
| `_fixture_catalogue.py`         | Strict pydantic v2 catalogue of Google Workspace fixtures |
| `provision_google_fixtures.py`  | Idempotent provisioner for every fixture in the catalogue |
| `teardown_google_fixtures.py`   | Recursive delete of the fixture tree + env-var clearing |

## Google Workspace test fixtures

The project's `@pytest.mark.live` test tier hits real Google APIs —
per `CLAUDE.md`, live tests **never** use mocks, patches, stubs, or
fakes. For contributors to run those tests locally, every Google code
path needs project-owned Drive / Sheets / Docs artefacts to read and
write against.

The fixture surface lives entirely under a single root Drive folder
(`aeat-test-fixtures`) owned by whichever Google account is resolved
by `aeat.auth.get_credentials_for_scopes`. Every fixture is **synthetic
only**: no real client data, no real AEAT response content, no real
PII ever ends up in a Google Workspace fixture. Review rejects any
change that violates that invariant.

### Prerequisites

1. A Google account (consumer or Workspace) and a GCP project configured
   through the chore/4 bootstrap chain:
   ```
   just gsuite-oauth-client
   just gcloud-auth
   just gsuite-enable-apis
   ```
2. `env/.env` populated from `env/.env.example`
   (`just env-setup`) with `GOOGLE_CLOUD_PROJECT` set.

### Provisioning your own fixture set

```bash
just google-fixtures-provision
```

What this does:

- Reads `scripts/_fixture_catalogue.py`.
- For each entry, resolves credentials via `aeat.auth`, builds the
  appropriate Drive / Sheets / Docs service, and **idempotently
  finds-or-creates** the resource under its parent (parent-first walk).
- Seeds freshly-created Sheets (`A1`) and Docs (body) with the inert
  sentinel `aeat-fixture-smoke-ok`. Existing resources are left
  untouched, so re-runs are non-destructive.
- Writes every resource ID back into `env/.env` against the
  `AEAT_GOOGLE_TEST_FIXTURE*` and `AEAT_GOOGLE_TEST_FIXTURES_FOLDER_ID`
  env vars.
- Prints a summary table with `created` / `existing` status per fixture.

Re-running the recipe on an already-provisioned account is a no-op
(modulo writing the same IDs back into `env/.env`).

### Running the live smoke test

The smoke test `tests/live/test_google_fixtures_smoke.py` is **dual
opt-in**: it is collected only when both of the following are truthy
in the environment:

- `AEAT_LIVE_TESTS_ENABLED` — the umbrella live-test flag
- `AEAT_LIVE_TESTS_GOOGLE` — the Google-specific flag

```bash
# Unix
AEAT_LIVE_TESTS_ENABLED=1 AEAT_LIVE_TESTS_GOOGLE=1 just test-live

# Windows (pwsh)
$env:AEAT_LIVE_TESTS_ENABLED='1'; $env:AEAT_LIVE_TESTS_GOOGLE='1'; just test-live
```

The dual opt-in exists so contributors who cannot authenticate to
Google can still run the rest of the live tier without the Google
smoke test failing them.

### Teardown

```bash
just google-fixtures-teardown
```

Permanently deletes the root fixture folder (Drive cascade removes
every descendant) and clears the `AEAT_GOOGLE_*` fixture env vars back
to empty. Safe to run on a machine that never provisioned fixtures —
it becomes a no-op on the Google side and only rewrites `env/.env`.

### Adding a new fixture

When a future issue needs a new live Google fixture:

1. Append a new `FixtureSpec` literal to `scripts/_fixture_catalogue.py`.
   Pick a stable kebab-case `fixture_id`, reference the root folder (or
   a deeper parent) via `parent_id`, and set `env_var_name` to a
   brand-new uppercase constant.
2. Add the matching field to `Settings` in `src/aeat/config.py` and
   the matching line to `env/.env.example`.
   (`tests/test_config.py` enforces alignment.)
3. Re-run `just google-fixtures-provision` — the find-or-create walk
   will leave existing fixtures untouched and only create the new one.
4. Extend `tests/live/test_google_fixtures_smoke.py` or add a
   dedicated live test that reads the new fixture.

See `.vault/adr/2026-04-12-google-fixtures-adr.md` for the full
decision record, including the scope-trimming rationale and the
synthetic-only invariant.
