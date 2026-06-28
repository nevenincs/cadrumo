---
tags:
  - "#plan"
  - "#google-fixtures"
date: 2026-04-12
modified: '2026-04-12'
related:
  - "[[2026-04-12-google-fixtures-adr]]"
  - "[[2026-04-12-google-fixtures-research]]"
  - "[[2026-04-12-gsuite-bootstrap-adr]]"
---

# google-fixtures plan: provision google workspace live-test fixtures

## Overview

Implement the fixture surface decided in `[[2026-04-12-google-fixtures-adr]]`.
Ship the minimum viable fixture set (root folder + one Sheet + one Doc), a
strict pydantic v2 catalogue, idempotent provisioning + teardown scripts
reusing chore/4's Google client, cross-platform `just` recipes, additive
settings + env alignment, one opt-in live smoke test, and a contributor
README.

## Phase 1 — execution steps

### Step 1 — errors + settings + env example

1. Add `FixtureProvisioningError` subclass to `src/aeat/errors.py`.
2. Add four fields to `Settings` in `src/aeat/config.py`:
   - `aeat_google_test_fixtures_folder_id`
   - `aeat_google_test_fixture_smoke_sheet_id`
   - `aeat_google_test_fixture_smoke_doc_id`
   - `aeat_live_tests_google` (bool)
3. Mirror each new var in `env/.env.example` under a new "Google test
   fixtures" section. `tests/test_config.py` alignment passes.

### Step 2 — fixture catalogue + scripts

1. Create `scripts/` directory.
2. `scripts/_fixture_catalogue.py` — strict pydantic v2 models:
   - `FixtureKind(StrEnum)` = {`DRIVE_FOLDER`, `SHEET`, `DOC`, `FORM`}.
   - `FixtureSpec(BaseModel, ConfigDict(strict=True, frozen=True, extra="forbid"))`.
   - `FixtureCatalogue(BaseModel, ...)` with
     `entries: dict[str, FixtureSpec]` and helpers (`root_folder_spec`,
     `children_of`, iterator).
   - Module-level `CATALOGUE` literal with the three decided fixtures.
3. `scripts/provision_google_fixtures.py`:
   - CLI entry point via `python scripts/provision_google_fixtures.py`.
   - Resolve credentials (`get_credentials_for_scopes`).
   - Build Drive / Sheets / Docs services.
   - Walk the catalogue in parent-first order (root folder → children).
   - Find-or-create by name/mime inside parent (idempotent, using the
     pattern from `aeat.entrypoints.cli.bootstrap`).
   - After creating a Sheet, seed `A1` via the Sheets API.
   - After creating a Doc, seed body via the Docs `batchUpdate` API.
   - Collect `(env_var_name, resource_id)` pairs and call
     `aeat.core.env_io.write_env_vars` to persist into `env/.env`.
   - Print a rich table with `fixture_id`, `kind`, `id`, `created|existing`.
4. `scripts/teardown_google_fixtures.py`:
   - Resolve credentials.
   - Delete the root folder (Drive cascade handles children) by the
     folder ID from `Settings`.
   - Clear the four fixture env vars from `env/.env`
     (set to empty via `write_env_vars`).

### Step 3 — justfile recipes

Add cross-platform `[unix]` + `[windows]` recipes:

- `just google-fixtures-provision` → `uv run python scripts/provision_google_fixtures.py`
- `just google-fixtures-teardown` → `uv run python scripts/teardown_google_fixtures.py`

### Step 4 — live smoke test

`tests/live/test_google_fixtures_smoke.py`:

- Module-level `sys.path.insert(0, str(SCRIPTS_DIR))` to import
  `_fixture_catalogue`.
- `@pytest.mark.live` on every test.
- Collection-time skip unless both `AEAT_LIVE_TESTS_ENABLED` and
  `AEAT_LIVE_TESTS_GOOGLE` are truthy.
- `test_root_folder_exists` — Drive `files.get` on the folder ID.
- `test_smoke_sheet_has_seed` — Sheets `values.get('A1')` ==
  seed sentinel.
- `test_smoke_doc_has_seed` — Docs `documents.get` → flatten body →
  contains seed sentinel.
- No mocks, no patches, no stubs.

### Step 5 — documentation

`scripts/README.md` — contributor-facing doc:

- What the fixture catalogue is.
- How to provision / teardown on a fresh Google account.
- Synthetic-only invariant.
- Dual opt-in for the smoke test.
- How to add a new fixture for a future issue.

### Step 6 — verify + code review

1. `just lint && just typecheck && just test && just hooks` all green.
2. Mandatory `vaultspec-code-review` skill pass.
3. Record outcome in exec step record.

## Plan review

**Reviewer:** autonomous end-to-end pipeline (per handover brief).
**Outcome:** approved.

- Scope matches issue #13 acceptance bullets 1:1.
- Fixture set is the minimum decided in the ADR; #10 / #11 fixtures
  deferred to their own PRs (additive to the catalogue).
- No overlap with feature-10 / -14 / -15 / -16 / -17 / -20 branch
  territory (no src/aeat/storage, no src/aeat/corpus, no tests/conftest.py,
  no src/aeat/browser, no src/aeat/i18n edits; scripts/ and tests/live/
  are new).
- Pydantic v2 strict mandate respected for every metadata record.
- Live-test mandates (no mocks, dual opt-in, `@pytest.mark.live`) honoured.
- Reuse of chore/4's client surface verified against
  `src/aeat/entrypoints/cli/bootstrap.py` patterns.

Proceeding to execution.
