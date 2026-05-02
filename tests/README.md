# AEAT test suite

Operator reference for the nine-marker pytest taxonomy, the permanent
live-write ban, the pytest-only posture, and the associated plugin
roster. See charter `#116` (live-AEAT-write safety charter),
`.vault/adr/2026-04-17-pytest-markers-adr.md` (marker taxonomy), and
`.vault/adr/2026-04-17-pytest-only-testing-adr.md` (pytest-only posture,
plugin set, coverage gate) for the authoritative specifications; this
file is the operator-facing summary.

## Marker taxonomy

Every test module declares module-level markers via a single
`pytestmark = [...]` assignment placed immediately after the module
docstring and imports:

```python
import pytest

pytestmark = [pytest.mark.unit, pytest.mark.domain_inbound]
```

Per-function access or domain markers are forbidden. Mixed-access
modules (for example one `unit` function next to one `live_read`
function) must be split into two files rather than overridden per
function.

### Axis A - access level (mutually exclusive; exactly one per test)

| Marker       | Semantics                                                                 | Selection example                        |
| :----------- | :------------------------------------------------------------------------ | :--------------------------------------- |
| `unit`       | Deterministic, no external I/O. Mocks and stubs are permitted.            | `uv run pytest -m unit` (default)        |
| `live_read`  | Talks to a real external service with read-shaped operations only.        | `uv run pytest -m live_read`             |
| `live_write` | Talks to a real external service with write-shaped operations. **Banned.** | `uv run pytest -m live_write` (see below) |

### Axis B - domain (at least one per test)

| Marker                   | Covers                                                                            | Selection example                                |
| :----------------------- | :-------------------------------------------------------------------------------- | :----------------------------------------------- |
| `domain_outbound`     | `auth`, `browser`, `casillas`, `inbox`, `justificante`, `portals`, `status`, `sync` | `uv run pytest -m "unit and domain_outbound"` |
| `domain_submission`      | `filing`, `submission` local export, preflight, and historical records             | `uv run pytest -m "unit and domain_submission"`  |
| `domain_inbound` | `financial`, `cli/financial`                                                       | `just test-domain financial_input`               |
| `domain_persistence`     | `storage`, `models`, `normatives`, `manuals`, `corpus`, `schema`, `deadlines`     | `just test-domain local_state`                   |
| `domain_application`       | `workflow`, `llm`, `i18n`, `testing`                                              | `just test-domain mediation`                     |
| `domain_core`           | root modules, non-domain `cli`, `setup`, top-level `tests/*.py`                    | `just test-domain infra`                         |

An additional `flaky` marker is registered for opt-in retry via
`pytest-rerunfailures`; it is permitted only on `live_read` / `live_write`
tests and must never be applied to `unit` tests or the whole suite.

## Module-level mandate

`tests/test_marker_integrity.py` walks every `test_*.py` and
`_test_*.py` module under `src/aeat/` and `tests/` via `ast` and fails
CI if any module lacks a compliant `pytestmark` assignment. The
collection hook (shared helper in `tests/_marker_hook.py`, invoked from
both the repo-root `conftest.py` and `tests/conftest.py`) additionally
raises `pytest.UsageError` at collection time if an item surfaces with
zero or more than one access marker or with no domain marker. Both
guards are in place because module-level declarations are the only
shape that yields predictable marker inheritance under pytest.

## live_write ban

`@pytest.mark.live_write` items are **dropped** (not skipped) from the
collection with no bypass. Drop-not-skip is intentional: skipped items
surface in pytest reports as "would have run if unskipped" and are a
single env-var flip away from executing. Dropped items are invisible
downstream of collection and cannot be reinstated by any marker-
expression flag.

Zero `live_write` tests exist in the repository today. The marker,
the collection ban, and this documentation are dormant infrastructure
shipped so any future write-shaped probe is required to carry the
marker and is permanently collection-banned. Charter `#116` R1 is
absolute: no automated test may ever produce a legally binding AEAT
filing.

There is no environment variable, confirmation phrase, CLI flag, or
interactive-terminal bypass for `live_write` collection.

## pytest-only posture

The project uses **pytest exclusively**. The `unittest` package, the
standard library's `unittest.mock`, and the third-party `mock` library
are **banned globally** by ruff rule `TID251`. There is no escape
hatch. Violations fail `just lint`, the pre-commit hook, and any local
ruff run.

Rationale: live-AEAT tests must not use mocks (charter `#116`). Banning
the primary mocking entrypoints globally closes the only path by which
a regression could reintroduce them to a live test file.

## Banned imports

### Globally (ruff `TID251`)

- `unittest`
- `unittest.mock`
- `mock`

Error message cites this file. Applies everywhere in the repo, source
and tests alike.

### In any file containing a `live_read` or `live_write` item

The conftest-level AST scanner additionally rejects these modules in
any test file that declares a `live_read` or `live_write` item:

- `pytest_mock`
- `responses`
- `httpx_mock`, `pytest_httpx`
- `vcr`, `vcrpy`
- `freezegun`, `time_machine`

Rationale: live tests must observe real external state — including
real clocks and real HTTP traffic. Snapshot/record libraries (`vcr`,
`pytest-httpx`) and time-control libraries (`time-machine`) are only
safe in unit tests. The scan is syntactic (AST); it does not execute
the file.

Constants live in `tests/conftest.py` as `LIVE_ACCESS_MARKERS`,
`BANNED_LIVE_IMPORTS`, and `LIVE_OPT_IN_ENV`.

## Live opt-in

`live_read` tests are skipped unless `AEAT_LIVE_TESTS_ENABLED=1` is
set in the environment. The canonical env var name is spelled
**`AEAT_LIVE_TESTS_ENABLED`** (not `AEAT_LIVE_TESTS`); it is the field
the pydantic `Settings` model in `src/aeat/config.py` reads.

The opt-in is enforced at two layers:

1. `pyproject.toml` sets `addopts = "... -m 'unit' ..."` so plain
   `just test` deselects `live_read` items.
2. `tests/conftest.py` layers on a runtime check: when live items are
   collected, it adds a `skip` marker with a clear reason if the env
   var is not truthy. This protects against ad-hoc
   `pytest -m live_read` invocations forgetting the opt-in.

Google Workspace live tests additionally require
`AEAT_LIVE_TESTS_GOOGLE=1` and project-owned fixtures provisioned via
`just google-fixtures-provision` (see `scripts/README.md`).

## Plugin roster

| plugin | scope | role | pitfalls |
| --- | --- | --- | --- |
| `pytest-asyncio` | unit + live | async test collection (`asyncio_mode = "strict"`) | strict mode means plain `async def` tests need an explicit `@pytest.mark.asyncio` |
| `pytest-playwright` | live only | browser fixtures (`page`, `browser`, `context`) | needs `playwright install` for browser binaries |
| `pytest-httpx` | unit only | httpx wire-shape assertions | **banned in live files** |
| `pytest-rerunfailures` | live only, opt-in per-test | retry intermittently flaky external endpoints | never apply globally; never apply to unit tests |
| `syrupy` | unit + live | snapshot diffing for large structured output | never `--snapshot-update` in CI; review diffs like code |
| `pytest-xdist` | unit only (opt-in via `just test-parallel`) | parallel unit suite | changes fixture-scope semantics; not safe for live |
| `pytest-cov` | unit only | coverage measurement + fail-under | excluded from live (see coverage gate) |
| `time-machine` | unit only | deterministic wall-clock control | **banned in live files** |

Notably **not adopted**: `pytest-sugar`, `pytest-rich`, `freezegun`,
`pytest-timeout`, `pytest-github-actions-annotate-failures` (Actions CI
is permanently disabled on this repo).

## Coverage gate

Starting threshold is **60%** against `src/aeat`, enforced by
`just test-cov` via `--cov-fail-under=60`. Branch coverage is enabled.
Test modules (`test_*.py`, `_test_*.py`, `tests/`) are omitted from
coverage.

Ratchet policy: the threshold only moves up. Lowering it requires a
new ADR with the rationale (e.g. temporary dip during a refactor); the
default posture is to delete dead code or add tests rather than relax
the floor.

## Recipes

- `just test` — unit suite (`-m 'unit'` via pyproject `addopts`). Skips live.
- `just test-live` — `unit or live_read`. Requires `AEAT_LIVE_TESTS_ENABLED=1`.
- `just test-live-read` — `live_read` only.
- `just test-domain DOMAIN` — `unit and domain_{{DOMAIN}}`.
- `just test-live-write` — documentation surface for the permanent live-write
  ban; returns zero collected.
- `just test-cov` — unit suite with coverage; fails if below 60%.
- `just test-parallel` — unit suite under xdist. Never on live.
- `just lint` — ruff, including the TID251 banned-import rule.
- `just hooks` — full prek pre-commit sweep.

## Writing a new test

Checklist:

1. Colocate unit tests with the module under test
   (`src/aeat/<pkg>/test_*.py`); put live tests in the same directory
   as their unit siblings.
2. Declare `pytestmark = [pytest.mark.<access>, pytest.mark.<domain>]`
   at module level. Never apply access or domain markers per function.
3. Never import `unittest` / `unittest.mock` / `mock`.
4. In `live_read` / `live_write` files, also never import any module
   from the extended banned set (`pytest_httpx`, `time_machine`, etc.).
5. For `live_read` / `live_write` tests that hit genuinely flaky
   endpoints, add `@pytest.mark.flaky(reruns=2)` on the individual
   test — not globally.
6. Run `just test` locally before pushing; run `just test-cov` to make
   sure the coverage floor still holds.

## Cross-references

- Charter `#116` - rules R1..R6 governing the live-write path.
- `.vault/adr/2026-04-17-pytest-markers-adr.md` - marker taxonomy decision.
- `.vault/adr/2026-04-17-pytest-only-testing-adr.md` - pytest-only
  posture, plugin set, coverage gate.
- `tests/_marker_hook.py` - shared collection hook body.
- `tests/test_marker_integrity.py` - AST-backed drift detector.
- `scripts/README.md` - Google Workspace fixture provisioning for
  `live_read` tests.
- `CLAUDE.md` - multilingual testing contract and module-layout mandate.
