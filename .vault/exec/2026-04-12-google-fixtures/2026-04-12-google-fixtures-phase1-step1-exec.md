---
tags:
  - "#exec"
  - "#google-fixtures"
date: 2026-04-12
modified: '2026-04-12'
related:
  - "[[2026-04-12-google-fixtures-plan]]"
  - "[[2026-04-12-google-fixtures-adr]]"
  - "[[2026-04-12-google-fixtures-research]]"
---

# google-fixtures phase1 step1 — provision fixture surface end-to-end

## Intent

Execute every step of `[[2026-04-12-google-fixtures-plan]]` in a single
phase: errors + settings + env example → catalogue + provisioning +
teardown scripts → justfile recipes → live smoke test → contributor
README → verify (lint / typecheck / test / hooks).

## Changes landed

### Core library (`src/aeat/`)

- `src/aeat/errors.py`: added `FixtureProvisioningError(AeatError)`
  domain subclass. Raised by the provisioning and teardown scripts
  exclusively — no bare `Exception` raises introduced.
- `src/aeat/config.py`: four additive `Settings` fields:
  `aeat_google_test_fixtures_folder_id`,
  `aeat_google_test_fixture_smoke_sheet_id`,
  `aeat_google_test_fixture_smoke_doc_id`,
  `aeat_live_tests_google: bool`. All default-empty / default-False so
  the alignment test `tests/test_config.py` passes unchanged.

### Env contract (`env/.env.example`)

- New "Google test fixtures" section documenting the three fixture ID
  env vars and `AEAT_LIVE_TESTS_GOOGLE`. Every Settings field has a
  matching example line; alignment test stays green.

### Scripts (`scripts/`) — new top-level directory

- `scripts/_fixture_catalogue.py` — strict pydantic v2 catalogue:
  `FixtureKind(StrEnum)`, `FixtureSpec` (strict/frozen/extra=forbid,
  kebab-case id validation, env-var name validation), `FixtureCatalogue`
  with `root_folder_spec()` and `children_of()`. Module-level
  `CATALOGUE` literal carries exactly three entries (root folder +
  smoke Sheet + smoke Doc) per the ADR's minimum-viable decision.
- `scripts/provision_google_fixtures.py` — reuses `aeat.adapters.outbound.aeat.auth`
  (`get_credentials_for_scopes`, `build_drive_service`,
  `build_sheets_service`, `build_docs_service`), walks the catalogue
  parent-first, find-or-creates each resource via a helper that
  mirrors `aeat.entrypoints.cli.bootstrap` dedup logic, seeds only freshly
  created Sheets (`values.update A1`) and Docs (`documents.batchUpdate
  insertText`), persists IDs via `aeat.core.env_io.write_env_vars`, prints
  a rich summary table. Raises `FixtureProvisioningError` on failure.
- `scripts/teardown_google_fixtures.py` — reads
  `Settings.aeat_google_test_fixtures_folder_id`, recursively deletes
  the folder via Drive's cascade (`files.delete`), then clears every
  fixture env var back to empty. No-op on machines that never ran
  provisioning.
- `scripts/README.md` — contributor-facing doc: prerequisites,
  provision / teardown recipes, dual opt-in for the smoke test,
  synthetic-only invariant, and how to add a new fixture.

### Justfile recipes

- `just google-fixtures-provision` — `[unix]` bash + `[windows]` pwsh
  wrapping `uv run python scripts/provision_google_fixtures.py`.
- `just google-fixtures-teardown` — analogous wrapper for teardown.
  Cross-platform parity follows the existing recipe conventions.

### Live smoke test (`tests/live/`)

- `tests/live/__init__.py` — empty marker file.
- `tests/live/test_google_fixtures_smoke.py`:
  - `pytestmark` = `[pytest.mark.live, skipif dual opt-in]` — collects
    only when `AEAT_LIVE_TESTS_ENABLED=1` **and**
    `AEAT_LIVE_TESTS_GOOGLE=1`.
  - Loads the fixture catalogue at runtime via `importlib.util` to
    avoid polluting `sys.path` with `scripts/` (keeps the type-checker
    happy without touching `[tool.ty] allowed-unresolved-imports`).
  - `test_fixture_catalogue_ids_are_populated` — guards the common
    "ran before provisioning" failure mode.
  - `test_root_folder_exists` — Drive `files.get`.
  - `test_smoke_sheet_has_sentinel` — Sheets `values.get A1`.
  - `test_smoke_doc_has_sentinel` — Docs `documents.get`, body flattened
    via helper.
  - `test_every_catalogued_child_lives_under_root` — Drive parent check
    to catch catalogue drift.
  - Zero mocks, patches, stubs, or fakes.

## Verification

Run locally on Windows (pwsh via bash shell):

- `uv run ruff check .` → **All checks passed!**
- `uv run ty check src tests` → **All checks passed!**
- `uv run pytest` → **97 passed, 1 skipped, 11 deselected** (1.80s).
  The 11 deselected include the new live Google smoke tests (dual
  opt-in skip). The 1 skipped is an unrelated pre-existing skip.
- `uv run prek run --all-files` → every hook (trim whitespace, EOL,
  yaml, toml, added large files, merge conflicts, private key, ruff,
  ruff format, ty) **passed**.

No lint / type / test / hook rule was suppressed or skipped. The one
pre-existing `noqa` in the teardown script was removed after ruff
flagged it as unneeded.

## Code review (inline, per the handover's mandatory review phase)

Walking every changed file against the project's core mandates:

- **Synthetic-only invariant** — every seed value in the catalogue is
  the inert sentinel `aeat-fixture-smoke-ok`. No real client data, no
  real AEAT content, no PII, no credential material.
- **Pydantic v2 strict mandate** — `FixtureSpec` and `FixtureCatalogue`
  use `ConfigDict(strict=True, frozen=True, extra="forbid")`.
  `FixtureKind` is a `StrEnum`. No bare `dict[str, Any]` in any public
  signature. `ProvisioningResult` is a `@dataclass(frozen=True)`
  internal value object (not boundary-crossing — lives and dies inside
  the provisioning script).
- **Typed signatures** — every public function in the scripts and the
  test carries full type hints. ty passes on `src tests`.
- **Google-style docstrings** — every module, class, and function has
  an Args/Returns/Raises block where applicable.
- **Error hierarchy** — `FixtureProvisioningError(AeatError)` is the
  only domain error raised; no bare `Exception`.
- **Logging** — provisioning and teardown use
  `aeat.core.logging.get_logger(__name__)`. No scattered
  `logging.getLogger(__name__)`.
- **Public API discipline** — no new module under `src/aeat/`; only an
  additive error subclass and additive Settings fields. `scripts/` is
  the documented escape hatch, not on the import path.
- **Branch-boundary respect** — untouched: `tests/conftest.py`
  (feature-15), `src/aeat/adapters/persistence/storage/` (feature-10), `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/`
  (feature-16), `src/aeat/core/i18n/` (feature-20), `src/aeat/corpus/`
  (feature-17), `src/aeat/domain/modelos/` (feature-6), `src/aeat/domain/portals/`
  (feature-7), `tests/fixtures/filing_history/` + `src/aeat/domain/testing/`
  (feature-14). Only additive edits to shared files
  (`src/aeat/config.py`, `src/aeat/errors.py`, `env/.env.example`,
  `justfile`).
- **Scope discipline** — every fixture in the catalogue has a concrete
  consumer (the smoke test). No fixtures provisioned "in case" a
  future issue needs them. #10 and #11 fixtures deferred to their own
  PRs as additive catalogue entries.
- **Live-test discipline** — `@pytest.mark.live`, dual opt-in, no
  mocks / patches / stubs / fakes, hit real Google services.
- **Reuse** — no new Google client surface defined; every API call
  goes through `aeat.adapters.outbound.aeat.auth.build_*_service` and
  `aeat.adapters.outbound.aeat.auth.get_credentials_for_scopes`.

**Review verdict: approved for merge.**

## Follow-ups (not blocking)

- When feature-10 lands a live storage test that wants a Sheet mirror,
  add a `FixtureSpec` entry and a matching Settings field.
- Same for feature-11 divergence sink.
- Neither is blocked by this PR.
