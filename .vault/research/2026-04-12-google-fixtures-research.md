---
tags:
  - "#research"
  - "#google-fixtures"
date: 2026-04-12
modified: '2026-04-12'
related:
  - "[[2026-04-12-gsuite-bootstrap-adr]]"
  - "[[2026-04-12-base-module-structure-adr]]"
  - "[[2026-04-12-dev-scaffolding-adr]]"
---

# google-fixtures research: scope discovery for live google workspace test surface

## Problem Statement

Issue #13 asks for a canonical set of Google Workspace test fixtures (Drive /
Sheets / Docs / Forms) that the project's `@pytest.mark.live` tests will read
and write against. `CLAUDE.md` forbids mocks in live tests, so every live path
that touches Google must hit a real, project-owned artefact. We need to decide
*which* fixtures are worth provisioning right now versus deferring until a
specific upstream test concretely needs them.

## Existing assets (chore/4, merged)

chore/4 already landed the full Google Workspace integration surface:

- `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/__init__.py` — credential resolver (`get_credentials_for_scopes`),
  scope constants, service builders (`build_drive_service`, `build_sheets_service`,
  `build_docs_service`).
- `src/aeat/entrypoints/cli/bootstrap.py` — the `aeat bootstrap` command already provisions
  a scratch folder / sheet / doc idempotently under the active credentials and
  writes the IDs back into `env/.env`. This is the blueprint this issue reuses.
- `src/aeat/entrypoints/cli/drive.py`, `sheets.py`, `docs.py` — typed Drive / Sheets / Docs
  CLI helpers.
- `src/aeat/env_io.py` — dependency-free `.env` rewriter (`write_env_vars`).
- `just gsuite-bootstrap` / `just gcloud-auth` — cross-platform bootstrap chain.

Any provisioning tooling shipped by this issue must **reuse** this surface.
Defining a second Google client surface would duplicate scopes, duplicate
credential resolution, and violate the single-chokepoint rule.

## Upstream fixture demand survey

| Issue  | Surface                          | In-repo fixture? | Google fixture? | Rationale |
| ------ | -------------------------------- | ---------------- | --------------- | --------- |
| #6     | Modelo enum catalogue            | yes (Python)     | no              | Pure in-code data; no Google interaction path. |
| #7     | Portal URL catalogue             | yes (Python)     | no              | Same — metadata is code, not a document. |
| #9     | Schema extraction (one modelo)   | yes (corpus PDF / HTML) | no       | Extractors read from `corpus/` (#17); Drive is not in the loop. |
| #10    | Storage backend                  | yes (SQLite / files) | yes (export target Sheet) | ADR in #10 is trending away from Sheets-as-primary, but an export-target Sheet validates the "mirror to Sheet" path when a tax preparer wants human inspection. Low-fidelity mirror only. |
| #11    | Self-healing sync                | yes (divergence record JSON) | yes (divergence sink Sheet) | A human-readable mirror of divergence records lets the user triage. The Sheet is not the source of truth — it is a tail-out. |
| #14    | Synthetic filing-history fixtures | yes (JSON)      | no              | Fixtures are hand-curated, in-repo, diff-friendly. A Sheet mirror adds complexity with no test consumer. |
| #15    | pytest-only testing              | n/a              | no              | Tooling concern. |
| #16    | Playwright anti-bot              | n/a              | no              | Browser concern, not Google. |
| #17    | Corpus rulebook                  | yes (`corpus/`)  | no              | The corpus is git-tracked for legal anchoring; Drive hosting would defeat that. |
| #20    | Trilingual i18n                  | yes (enum + models) | no           | Pure types. |
| #21    | LLM client chokepoint            | n/a              | no              | Wire-level concern. |
| #23    | Casilla DB                       | yes (JSON per modelo) | no         | Reviewed by humans via git; no Drive component. |
| #25    | Manual practico                  | yes (`corpus/manuals/`) | no       | Same as #17. |

### Near-term fixture set

Of the two "maybe" candidates (#10 export Sheet, #11 divergence Sheet), **both
are in progress and neither has a live test yet**. Per the issue's explicit
guidance ("resist the temptation to invent fixtures that no test actually
consumes" and "ship FEWER, not more"), we defer #10 / #11 fixture provisioning
until those issues reach the live-test phase — they add `FixtureSpec` entries
to the catalogue additively when needed.

What this issue *must* ship now, to prove the provisioning tooling end-to-end
and to give #10 / #11 a zero-friction path to extend:

1. **Root Drive folder** `aeat-test-fixtures` owned by the project account.
2. **One Sheet fixture** `aeat-test-smoke-sheet` with seeded cell `A1 =
   "aeat-fixture-smoke-ok"` — validates the Sheets read path.
3. **One Doc fixture** `aeat-test-smoke-doc` with seeded body
   `"aeat-fixture-smoke-ok"` — validates the Docs read path.

Three fixtures is the minimum that exercises both the Drive traversal, the
Sheets read path, and the Docs read path in a single opt-in smoke test. Any
subsequent issue that needs a new fixture appends a `FixtureSpec` entry to
`scripts/_fixture_catalogue.py` and re-runs `just google-fixtures-provision`.

## Synthetic-only invariant

Every Google Workspace fixture provisioned by this issue contains only
**synthetic** content authored by the provisioning script. No real client
filing, no real AEAT response body, no real credential, no real PII ever
touches a Google Workspace fixture. The seeded sentinel `aeat-fixture-smoke-ok`
is deliberately inert.

## Tooling location trade-off

CLAUDE.md mandates all Python modules live under `src/aeat/`. The provisioning
script, however, is one-shot dev tooling — not library code consumed at
runtime by the package. `scripts/` is the project's documented escape hatch
for non-src Python tooling (no existing `scripts/` directory in this worktree;
this issue creates it). The alternative — adding a new subpackage such as
`src/aeat/fixtures/` — would expose test-only provisioning logic on the
importable public surface, and would collide with feature-14's ownership of
`src/aeat/domain/testing/`. **Decision: ship the provisioning tooling under
`scripts/`.** The catalogue lives as a Python literal at
`scripts/_fixture_catalogue.py` (strict pydantic v2 models) so review and diff
are trivial.

The smoke test lives at `tests/live/test_google_fixtures_smoke.py`
(per the issue's acceptance wording) and imports the catalogue via a small
`sys.path` adjustment inline — no new conftest is introduced, avoiding any
collision with feature-15's ownership of `tests/conftest.py`.

## Live-test opt-in policy

`AEAT_LIVE_TESTS_ENABLED=1` already exists (chore/4) as the single opt-in for
every live test. Issue #13 calls for a **dual** opt-in for Google specifically,
so contributors can run the full live suite while excluding Google. The second
flag is `AEAT_LIVE_TESTS_GOOGLE=1`. The smoke test skips unless both are set.

## Reuse summary (what we do NOT re-implement)

- Credential resolution: use `aeat.adapters.outbound.aeat.auth.get_credentials_for_scopes`.
- Drive / Sheets / Docs service builders: use `aeat.adapters.outbound.aeat.auth.build_*_service`.
- Idempotent find-or-create: reuse the pattern from `aeat.entrypoints.cli.bootstrap`.
- `.env` rewrite: use `aeat.core.env_io.write_env_vars`.
- Scopes: use `DRIVE_SCOPE`, `SHEETS_SCOPE`, `DOCS_SCOPE`.

## Open questions (none blocking)

- If #10 lands before this issue ships, we still defer its fixture to the #10
  PR itself. This issue ships the catalogue *shape* that #10 will extend.
