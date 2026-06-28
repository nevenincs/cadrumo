---
tags:
  - "#adr"
  - "#google-fixtures"
date: 2026-04-12
modified: '2026-04-12'
related:
  - "[[2026-04-12-google-fixtures-research]]"
  - "[[2026-04-12-gsuite-bootstrap-adr]]"
  - "[[2026-04-12-base-module-structure-adr]]"
---

# google-fixtures adr: canonical google workspace test fixture surface | (**status:** `accepted`)

## Context

Per issue #13, live integration tests (`@pytest.mark.live`) that exercise
Google Workspace code paths must hit real, project-owned artefacts — mocking
is banned project-wide in the live tier. The Google auth / service surface
already exists (chore/4); what is missing is a **catalogued, idempotent,
reproducible** set of Drive / Sheets / Docs fixtures that those live tests
can read from.

## Decision

### D1 — Fixture set (minimum viable, near-term)

Ship the minimum set that exercises the Drive traversal + Sheets read +
Docs read paths end-to-end in a single opt-in smoke test:

- Drive folder `aeat-test-fixtures` (root for every fixture)
- Sheet `aeat-test-smoke-sheet` with seeded cell `A1 = "aeat-fixture-smoke-ok"`
- Doc `aeat-test-smoke-doc` with seeded body `"aeat-fixture-smoke-ok"`

Additional fixtures for #10 (storage export Sheet) and #11 (divergence sink
Sheet) are **deferred** to those issues' own PRs — they append
`FixtureSpec` entries to the catalogue additively when their live tests
land. See `[[2026-04-12-google-fixtures-research]]` decision matrix.

### D2 — Fixture metadata is strict pydantic v2

Every fixture is described by a frozen, strict `FixtureSpec` pydantic v2
model. A `FixtureCatalogue` model wraps the collection as
`dict[str, FixtureSpec]` keyed by stable kebab-case `fixture_id`.
Closed enumerations (`FixtureKind`) are `enum.StrEnum`. No bare dicts cross
any boundary. The catalogue lives in Python literals at
`scripts/_fixture_catalogue.py` so review and diff are trivial.

This is driven by the project-wide pydantic mandate (see the pinned
comment on #13). It is not optional.

### D3 — Reuse chore/4's Google client surface

The provisioning and teardown scripts MUST reuse:

- `aeat.adapters.outbound.aeat.auth.get_credentials_for_scopes` (credential resolver)
- `aeat.adapters.outbound.aeat.auth.build_drive_service` / `build_sheets_service` / `build_docs_service`
- `aeat.adapters.outbound.aeat.auth.DRIVE_SCOPE` / `SHEETS_SCOPE` / `DOCS_SCOPE`
- `aeat.core.env_io.write_env_vars` (idempotent env rewrite)
- The idempotent find-or-create pattern from `aeat.entrypoints.cli.bootstrap`

No competing Google client is defined. No parallel credential resolver.

### D4 — Tooling lives under `scripts/`

Provisioning and teardown ship as standalone Python scripts in a new
top-level `scripts/` directory (the project's documented non-src escape
hatch). The catalogue (`scripts/_fixture_catalogue.py`), the provisioner
(`scripts/provision_google_fixtures.py`), the teardowner
(`scripts/teardown_google_fixtures.py`), and a contributor README
(`scripts/README.md`) all live there.

Rejected alternatives:

- `src/aeat/fixtures/` — would leak test-provisioning logic onto the
  library's importable surface.
- `src/aeat/domain/testing/` — feature-14 owns this subpackage; touching it would
  cross branch boundaries.

### D5 — Errors inherit from `AeatError`

A new `FixtureProvisioningError` is added to `src/aeat/errors.py`.
Provisioning and teardown raise only this class (or stdlib
OS/auth errors surfaced verbatim for failure clarity).

### D6 — Dual opt-in for Google live tests

The existing `AEAT_LIVE_TESTS_ENABLED` (chore/4) remains the umbrella
live-test opt-in. A new `AEAT_LIVE_TESTS_GOOGLE` flag is added so
contributors who can run other live tests but lack a Google account
can skip Google fixtures specifically. The smoke test is collected only
when **both** flags are true.

### D7 — Settings additions (additive, alignment-tested)

`src/aeat/config.py` gains:

- `aeat_google_test_fixtures_folder_id: str`
- `aeat_google_test_fixture_smoke_sheet_id: str`
- `aeat_google_test_fixture_smoke_doc_id: str`
- `aeat_live_tests_google: bool`

`env/.env.example` mirrors them. `tests/test_config.py` already
enforces alignment — no changes needed to the test itself.

### D8 — `just` recipes (cross-platform)

Two new recipes wrapping the scripts:

- `just google-fixtures-provision`
- `just google-fixtures-teardown`

Both use the same `[unix]` bash / `[windows]` pwsh split as existing
recipes, invoking `uv run python scripts/provision_google_fixtures.py`.

### D9 — Synthetic-only invariant (absolute)

No real client data, real AEAT response content, real PII, or real
credential material ever touches any Google Workspace fixture
provisioned by this issue. The seeded sentinel `aeat-fixture-smoke-ok`
is deliberately inert and machine-generated. Code review rejects any
change that introduces non-synthetic content to a fixture.

## Consequences

**Positive**

- Single source of truth for fixture identity (the pydantic catalogue).
- Idempotent provisioning — re-runs discover existing resources by name
  and rewrite the same IDs, matching the `aeat bootstrap` pattern.
- Zero duplication of Google client surface.
- Extension cost for a new fixture is one `FixtureSpec` entry.

**Negative / trade-offs**

- Contributors without Google credentials cannot run the smoke test.
  Mitigated by the dual opt-in: the test is cleanly skipped by default.
- `scripts/` is a second Python location (beyond `src/aeat/` and
  `tests/`); future contributors must know the convention. Documented in
  `scripts/README.md`.

## Status

`accepted` — proceed to `[[2026-04-12-google-fixtures-plan]]`.
