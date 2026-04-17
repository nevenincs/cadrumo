# AEAT test suite

This document is the single authoritative reference for the testing rules of
the `aeat` project. It consolidates the enforcement set introduced by
[Issue #15](https://github.com/wgergely/aeat/issues/15) and locked in by
[`.vault/adr/2026-04-17-pytest-only-testing-adr.md`](../.vault/adr/2026-04-17-pytest-only-testing-adr.md).

## pytest-only posture

The project uses **pytest exclusively**. The `unittest` package, the standard
library's `unittest.mock`, and the third-party `mock` library are **banned
globally** by ruff rule `TID251`. There is no escape hatch. Violations fail
`just lint`, the pre-commit hook, and any local ruff run.

Rationale: live-AEAT tests must not use mocks (see the live-write safety
charter in `.vault/adr/2026-04-16-live-write-test-audit-adr.md`). Banning the
primary mocking entrypoints globally closes the only path by which a
regression could reintroduce them to a live test file.

## Marker discipline

Every test must carry **exactly one** of:

- `@pytest.mark.unit` — deterministic, no external I/O.
- `@pytest.mark.live` — hits a real external system (AEAT, Google APIs, real
  browser, real network).

Missing or duplicate markers fail collection with a hard `pytest.exit`. The
check lives in `tests/conftest.py::pytest_collection_modifyitems` and runs
`tryfirst=True` so it sees every item before any filter deselects.

A third marker, `@pytest.mark.flaky(reruns=N)`, is registered for use **only
on live tests** that genuinely need per-test retries against intermittent
external endpoints. It must never be applied to unit tests.

## Banned imports

### Globally (ruff `TID251`)

- `unittest`
- `unittest.mock`
- `mock`

Error message cites this file. Applies everywhere in the repo, source and
tests alike.

### In any file containing a `@pytest.mark.live` item

The conftest-level AST scanner also rejects these additional modules in any
test file that declares a live-marked item:

- `pytest_mock`
- `responses`
- `httpx_mock`, `pytest_httpx`
- `vcr`, `vcrpy`
- `freezegun`, `time_machine`

Rationale: live tests must observe real external state — including real
clocks and real HTTP traffic. Snapshot/record libraries (`vcr`,
`pytest-httpx`) and time-control libraries (`time-machine`) are only safe in
unit tests. The scan is syntactic (AST); it does not execute the file.

Constants live in `tests/conftest.py` as `REQUIRED_MARKERS`,
`BANNED_LIVE_IMPORTS`, and `LIVE_OPT_IN_ENV`.

## Live opt-in

Live tests are skipped unless `AEAT_LIVE_TESTS_ENABLED=1` is set in the
environment. The canonical env var name is spelled **`AEAT_LIVE_TESTS_ENABLED`**
(not `AEAT_LIVE_TESTS`); it is the field the pydantic `Settings` model in
`src/aeat/config.py` reads.

The opt-in is enforced at two layers:

1. `pyproject.toml` sets `addopts = "... -m 'not live' ..."` so plain
   `just test` deselects live items.
2. `tests/conftest.py` layers on a runtime check: when live items are
   collected, it adds a `skip` marker with a clear reason if the env var
   is not truthy. This protects against ad-hoc `pytest -m live` invocations
   forgetting the opt-in.

Google Workspace live tests additionally require `AEAT_LIVE_TESTS_GOOGLE=1`
and project-owned fixtures provisioned via `just google-fixtures-provision`
(see `scripts/README.md` and
`.vault/adr/2026-04-12-google-fixtures-adr.md`).

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
`pytest-timeout`, `pytest-github-actions-annotate-failures` (Actions CI is
permanently disabled on this repo).

## Coverage gate

Starting threshold is **60%** against `src/aeat`, enforced by
`just test-cov` via `--cov-fail-under=60`. Branch coverage is enabled.
Test modules (`test_*.py`, `_test_*.py`, `tests/`) are omitted from coverage.

Ratchet policy: the threshold only moves up. Lowering it requires a new ADR
with the rationale (e.g. temporary dip during a refactor); the default
posture is to delete dead code or add tests rather than relax the floor.

## Recipes

- `just test` — unit suite. Skips live. Strict markers.
- `just test-live` — live suite. Requires `AEAT_LIVE_TESTS_ENABLED=1`.
- `just test-cov` — unit suite with coverage; fails if below 60%.
- `just test-parallel` — unit suite under xdist. Never on live.
- `just lint` — ruff, including the TID251 banned-import rule.
- `just hooks` — full prek pre-commit sweep.

## Writing a new test

Checklist:

1. Colocate unit tests with the module under test
   (`src/aeat/<pkg>/test_*.py`); put live tests in the same directory as
   their unit siblings.
2. Add exactly one of `@pytest.mark.unit` / `@pytest.mark.live` to every
   test function.
3. Never import `unittest` / `unittest.mock` / `mock`.
4. In live files, also never import any module from the extended banned set
   (`pytest_httpx`, `time_machine`, etc.).
5. For live tests that hit genuinely flaky endpoints, add
   `@pytest.mark.flaky(reruns=2)` on the individual test — not globally.
6. Run `just test` locally before pushing; run `just test-cov` to make sure
   the coverage floor still holds.
