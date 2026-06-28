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
  - "[[2026-04-12-google-fixtures-phase1-step1-exec]]"
---

# google-fixtures phase1 summary

## Status

`complete` — every acceptance bullet from issue #13 is satisfied; lint,
typecheck, pytest, and hooks are green on Windows. Ready for PR.

## Artefacts produced

- **Research** — `[[2026-04-12-google-fixtures-research]]`
- **ADR** — `[[2026-04-12-google-fixtures-adr]]`
- **Plan** — `[[2026-04-12-google-fixtures-plan]]`
- **Step record** — `[[2026-04-12-google-fixtures-phase1-step1-exec]]`

## Code landed

- `src/aeat/errors.py` — additive `FixtureProvisioningError(AeatError)`.
- `src/aeat/config.py` — four additive `Settings` fields for the
  fixture IDs + `AEAT_LIVE_TESTS_GOOGLE`.
- `env/.env.example` — mirrored entries under a new "Google test
  fixtures" section.
- `scripts/_fixture_catalogue.py` — strict pydantic v2 fixture
  catalogue with three entries (root folder, smoke Sheet, smoke Doc).
- `scripts/provision_google_fixtures.py` — idempotent provisioner
  reusing `aeat.adapters.outbound.aeat.auth` and `aeat.core.env_io`.
- `scripts/teardown_google_fixtures.py` — recursive delete +
  env-var clear, no-op when no fixture has been provisioned.
- `scripts/README.md` — contributor-facing doc.
- `justfile` — `google-fixtures-provision` and
  `google-fixtures-teardown` recipes (`[unix]` bash + `[windows]` pwsh).
- `tests/live/__init__.py` + `tests/live/test_google_fixtures_smoke.py`
  — dual-opt-in live smoke test exercising Drive / Sheets / Docs read
  paths.

## Verification

- `uv run ruff check .` — all checks passed.
- `uv run ty check src tests` — all checks passed.
- `uv run pytest` — **97 passed, 1 skipped, 11 deselected** (live tier
  skipped under the default dual opt-in).
- `uv run prek run --all-files` — every hook passed (trim whitespace,
  EOF, yaml, toml, large-files, merge-conflicts, private-key, ruff,
  ruff format, ty).

## Acceptance matrix (issue #13)

| Acceptance bullet | Evidence |
| ----------------- | -------- |
| Vault research + ADR capturing fixtures needed and rationale | `[[2026-04-12-google-fixtures-research]]` + `[[2026-04-12-google-fixtures-adr]]` |
| Idempotent provisioning + teardown scripts | `scripts/provision_google_fixtures.py`, `scripts/teardown_google_fixtures.py` — find-or-create by title under parent, seeds freshly-created only |
| Settings + env/.env.example updated + alignment test green | `src/aeat/config.py` + `env/.env.example` + `tests/test_config.py` passing |
| At least one `@pytest.mark.live` smoke test skipped by default | `tests/live/test_google_fixtures_smoke.py` (dual opt-in) |
| Documentation for contributor provisioning in own Google account | `scripts/README.md` |

## Branch boundary audit

Untouched areas: `tests/conftest.py`, `pyproject.toml` pytest/ty
config sections, `src/aeat/adapters/persistence/storage/`, `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/`,
`src/aeat/core/i18n/`, `src/aeat/corpus/`, `src/aeat/domain/modelos/`,
`src/aeat/domain/portals/`, `src/aeat/domain/testing/`, `tests/fixtures/`. Only
additive edits to genuinely shared files.

## Scope-trim rationale (issue #13, "ship FEWER")

Discovery flagged #10 and #11 as "maybe" fixture consumers but neither
has a live test yet. This PR ships the minimum catalogue (3 entries)
that exercises the entire Google integration path and defers #10 /
#11 fixtures to those issues' own PRs — they extend the catalogue
additively.
