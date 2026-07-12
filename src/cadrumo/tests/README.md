# AEAT test suite

Operator reference for the pytest topology, hexagonal marker taxonomy,
live-read opt-in, pytest-only posture, and plugin roster.

## Test topology

Every Python test module under `src/aeat` lives inside a directory named
`tests`, at the narrowest owning package or architectural boundary.

Examples:

```text
src/aeat/domain/modelos/tests/test_work_unit.py
src/aeat/application/modelo/tests/test_work_addressing.py
src/aeat/entrypoints/cli/tests/test_modelo_work_ux.py
src/aeat/tests/test_marker_integrity.py
```

Test module filenames must start with `test_`. `_test_*.py` and
`*_test.py` modules are invalid. A single small test file still gets a
local `tests` directory; naked colocated tests beside production modules
are not allowed.

## Marker taxonomy

Every test module declares module-level markers via a single
`pytestmark = [...]` assignment placed immediately after the module
docstring and imports:

```python
import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]
```

Per-function execution or hexagonal layer markers are forbidden. Mixed
execution-scope modules must be split into separate files.

### Execution Scope

| Marker | Semantics | Selection example |
| --- | --- | --- |
| `unit` | Deterministic offline tests for one layer or narrow behavior. | `uv run pytest -m unit` |
| `integration` | Deterministic offline tests that compose project layers. | `uv run pytest -m integration` |
| `aeat_live` | Opt-in read-only tests against a real external service. | `uv run pytest -m aeat_live` |

Automated AEAT write-shaped tests remain forbidden. There is no
selectable write-test marker or write-test lane.

### Hexagonal Layer

Each module carries exactly one layer marker:

| Marker | Covers |
| --- | --- |
| `hex_domain` | `domain.*` business model and calculation rules. |
| `hex_application` | `application.*` use cases and orchestration. |
| `hex_inbound_adapter` | `adapters.inbound.*` parsing/import boundaries. |
| `hex_outbound_adapter` | `adapters.outbound.*` service/export/browser boundaries. |
| `hex_persistence_adapter` | `adapters.persistence.*` storage boundaries. |
| `hex_entrypoint` | `entrypoints.*` command and presentation surfaces. |
| `hex_core` | `core.*` foundational cross-cutting utilities and central test harnesses. |

## Enforcement

`src/aeat/tests/test_marker_integrity.py` walks `test_*.py` modules under
`src/aeat` via `ast` and fails if any module violates placement,
filename, module-level marker, execution-scope, hex-layer, or retired
marker rules.

The collection hook in `aeat.tests._marker_hook`, invoked from both the
repo-root `conftest.py` and `src/aeat/tests/conftest.py`, also raises
`pytest.UsageError` during collection when a test item lacks exactly one
execution marker or exactly one accepted `hex_*` marker.

## Live Read Opt-In

`aeat_live` tests are skipped unless `AEAT_LIVE_TESTS_ENABLED=1` is set
in the environment. The canonical env var name is
`AEAT_LIVE_TESTS_ENABLED`.

The opt-in is enforced at two layers:

1. `pyproject.toml` sets `addopts = "... -m 'unit' ..."` so plain local
   test runs select only unit tests.
2. `src/aeat/tests/conftest.py` adds a skip marker to collected
   `aeat_live` items when the env var is not truthy.

Google Workspace live tests additionally require
`AEAT_LIVE_TESTS_GOOGLE=1` and project-owned fixtures provisioned via
the Google fixture workflow.

## Banned Imports

The project uses pytest exclusively. The standard library `unittest`,
`unittest.mock`, and the third-party `mock` library are banned by ruff
rule `TID251`.

Files containing `aeat_live` tests are also AST-scanned at collection
time for these banned test-control libraries:

- `pytest_mock`
- `responses`
- `httpx_mock`, `pytest_httpx`
- `vcr`, `vcrpy`
- `freezegun`, `time_machine`

Live tests must observe real external state. Snapshot/record libraries
and clock-control libraries belong only in deterministic offline tests.

## Plugin Roster

| plugin | scope | role | pitfalls |
| --- | --- | --- | --- |
| `pytest-asyncio` | unit + integration + live | async test collection (`asyncio_mode = "strict"`) | plain `async def` tests need an explicit async marker |
| `pytest-playwright` | live only | browser fixtures (`page`, `browser`, `context`) | needs `playwright install` for browser binaries |
| `pytest-httpx` | offline only | httpx wire-shape assertions | banned in `aeat_live` files |
| `pytest-rerunfailures` | live only, opt-in per-test | retry intermittently unstable external endpoints | never apply globally |
| `syrupy` | offline + live | snapshot diffing for large structured output | never update snapshots in CI |
| `pytest-xdist` | offline only | parallel deterministic suite | not safe for live tests |
| `pytest-cov` | unit only | coverage measurement and fail-under | live tests are excluded from the coverage lane |
| `time-machine` | offline only | deterministic wall-clock control | banned in `aeat_live` files |

## Coverage Gate

Starting threshold is 60% against `src/aeat`, enforced by the coverage
lane. Branch coverage is enabled. Test modules are omitted from
coverage through the `tests` topology and `test_*.py` file pattern.

Ratchet policy: the threshold only moves up. Lowering it requires a
documented rationale.

## Recipes

- `just test-unit` - unit suite (`-m 'unit'` via pyproject `addopts`).
- `uv run pytest -m integration` - deterministic cross-layer tests.
- `uv run pytest -m aeat_live` - live read-only tests; requires
  `AEAT_LIVE_TESTS_ENABLED=1`.
- `uv run pytest -m "unit and hex_domain"` - unit tests for the domain layer.
- `uv run pytest -m "integration and hex_entrypoint"` - CLI integration tests.
- `just test-coverage` - unit suite with coverage.
- `uv run pytest -n auto -m unit` - unit suite under xdist. Never use for live tests.
- `just check-style` - ruff, including the banned-import rule.
- `just check-pre-commit` - full pre-commit sweep.

## Writing A New Test

Checklist:

1. Place the test in the owning package's `tests` child directory.
2. Name the module `test_<topic>.py`.
3. Declare exactly one execution marker and at least one hex layer marker
   at module level.
4. Use `unit` for deterministic narrow tests, `integration` for
   deterministic cross-layer tests, and `aeat_live` only for read-only
   external-service tests.
5. Never import `unittest`, `unittest.mock`, or `mock`.
6. In `aeat_live` files, also avoid the extended banned set
   (`pytest_httpx`, `time_machine`, `vcr`, and related libraries).
7. Run the relevant focused pytest lane before closing a change.

## Cross-References

- `src/aeat/tests/_marker_hook.py` - shared collection hook body.
- `src/aeat/tests/test_marker_integrity.py` - AST-backed drift detector.
- `pyproject.toml` - pytest discovery, marker registry, and coverage
  omit settings.
