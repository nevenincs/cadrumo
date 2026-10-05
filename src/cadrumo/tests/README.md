# AEAT test suite

Operator reference for the pytest topology, hexagonal marker taxonomy,
live-read opt-in, pytest-only posture, and plugin roster.

## Test topology

Every Python test module under `src/cadrumo` lives inside a directory named
`tests`, at the narrowest owning package or architectural boundary.

Examples:

```text
src/cadrumo/domain/modelos/tests/test_work_unit.py
src/cadrumo/application/modelo/tests/test_work_addressing.py
src/cadrumo/entrypoints/cli/tests/test_modelo_work_ux.py
src/cadrumo/tests/test_marker_contract_enforcement.py
```

Test module filenames must start with `test_`. `_test_*.py` and
`*_test.py` modules are invalid. A single small test file still gets a
local `tests` directory; naked colocated tests beside production modules
are not allowed.

## Runtime test lifetimes

Do not start a shared runtime before running pytest. Unit tests exercise contracts
and isolated behavior without a background runtime. Integration fixtures that need
native IPC or profile workers start their own runtime/server in a temporary
synthetic storage root, wait for verified transport readiness, and stop and reap
their resources during teardown, including failures and cancellation. Test-owned
startup and cleanup are permitted; they do not install a service or introduce
product autostart or health management. Never point fixtures at a developer's
existing runtime or private profile root.

The native launch-door tests own finite child processes through `_fixture`;
installed-entrypoint tests use `launch` with an `ExitStack`; authenticated CLI/MCP
tests use `native_api_cli_session` and `NativeRuntimeFixtureOwner`. Preserve these
owners when adding tests so teardown also runs when setup or assertions fail.
Installed-entrypoint checks must use the installed executable and real bootstrap.
Tests that bind `ProfileWorkerCustody` directly must run that body in a disposable
child process: its immutable profile binding deliberately survives custody close.
Do not reset that production binding to make a later test pass. Publish file-based
readiness payloads atomically so existence also means the full payload is readable.

Run both runtime test scopes explicitly; the default pytest selection is unit-only:

```powershell
uv run pytest -n0 -m 'unit or integration' src/cadrumo/application/runtime/tests src/cadrumo/adapters/local_runtime/tests src/cadrumo/entrypoints/runtime/tests --durations=20
```

Native platform skips are coverage limits, not successful cross-platform checks.
OS-keychain cases require the interactive session capability described below.
Measure cold startup separately from request execution. Registry preparation
must finish before a fixture exposes transport readiness. Installed-runtime
fixtures allow 60 seconds for cold bootstrap; request deadlines stay independent.
Diagnose and record startup phases before changing a setup budget, and never
substitute a fixture server to conceal an installed-runtime startup failure.

For manual CLI/TUI/MCP testing, explicitly run `cadrumo-runtime` in a separate
development terminal with the same absolute storage root, native endpoint storage
identity and installed product version as the client. Its required arguments are
`--storage-root`, `--storage-identity` and `--expected-version`. Stop that owned
runtime when the development session ends. Clients only connect; they do not
start or repair it. Application provisioning will define the eventual launch policy.
Load local development environment values explicitly, for example with
`uv run --env-file env/.env cadrumo-runtime ...`; product settings do not read
dotenv files themselves. Session-admission overrides belong to the runtime owner,
and tests must select their intended policy explicitly rather than inherit a
developer's local override.

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

### Supplementary labels

A supplementary label rides *alongside* an execution marker; it never
replaces one. Unlike the two tiers above it may be declared per class or
per function, so a module can hold both labelled and unlabelled cases.

| Label | Marks | Enrol with |
| --- | --- | --- |
| `docs` | Documentation build, stubs, and docstring structure. | `-m docs` |
| `serial` | Isolation-sensitive tests that mutate process-global state; they flake under `-n auto`. | `just test-integration-serial` |
| `perf` | Performance acceptance gates. | the dispatch-only ci-full lane |
| `external_tool` | Tests needing a tool or data the dependency set does not install (LibreOffice; the npm Hunspell dictionaries; a real PowerShell on POSIX; a stock OpenSSL; an explicitly selected native macOS peer fixture or disposable GNOME Secret Service collection). | `just test-workbook-parity`, `just test-locale-spelling`, `just test-powershell-literal`, `just test-calculation-summary-pdf`, `just test-native-host-facilities` |
| `os_keychain` | Tests whose assertion subject is the OS credential store itself. | `just test-os-keychain` |
| `windows_only` | Tests whose subject exists only on Windows (console launcher stubs, the native runtime, process and login surfaces). | `just test-windows` |
| `resident_service` | Tests that query the running resident search service. | `just test-resident-service` |
| `private_ingest_corpus` | Tests that score the ingestion harness against the external measurement corpus named by `CADRUMO_INGEST_CORPUS_ROOT`; they fail, never skip, without it. | `just test-ingest-corpus` |

Ordinary lanes exclude the capability labels, so the label—not a path
`--ignore`—is what holds those tests out.

`just test-native-host` selects the explicit Unix runtime and custody cohort
for native-host verification, using the existing `unit` and `integration`
markers and excluding `os_keychain` tests.

Read `os_keychain` as a capability of the **logon session**, not of the
dependency set. A headless continuous-integration runner, and an agent
reaching the host over SSH, each hold a network logon that carries no
credentials: a real credential backend is selected and then refuses
every call, so no session key can be custodied there at all. Run these
tests from an interactive desktop session. Selected on a host that
cannot custody one, each case that needs the store is skipped at an
explicit precondition, `require_os_credential_store()`, under an
`OsCredentialStoreRefusedWarning` naming the measured refusal - a true
report of the host, never a defect and never coverage. The precondition
is called per case, not keyed on the label, so a labelled case that
asserts the refusal path itself still runs there.

Label only what is irreducibly capability-bound. A case provable
*without* the capability must stay unlabelled, or it silently leaves
every automated lane.

#### `os_keychain` is a standing coverage hole

Say it plainly, because no automated lane will: **the `os_keychain` cases
require a separate interactive-desktop verdict.** CI cannot run them, no agent host can run
them, and they were excluded from every lane precisely because a host
that cannot custody a session key can never pass them. Nothing in the
automated suite covers profile-session custody today.

This was the right trade against the alternative - a test-support
credential backend would be a production-shaped fake, and writing both
halves of the split-knowledge pair to disk would make the assertion
vacuous - but a trade is not a fix. The cases guard a security-critical
fail-closed path, so treat the hole as live risk rather than as settled.

Closing it takes one run of `just test-os-keychain` from an interactive
desktop session. Read that as a **recurring** obligation, not a one-time
sign-off: every change to login, logout, session resume, or session-key
custody re-opens the hole, and only a desktop run closes it again. A
green run once does not vouch for the code as it stands now.

Two gates keep the hole from going unnoticed.
`dev/ci/tests/test_os_keychain_lane_scope.py` refuses a labelled case
that sits outside the paths `just test-os-keychain` names, and
`dev/tests/test_lane_reachability.py` requires every test no automated
lane can run to carry a label naming why. Neither pins which cases may
take the label, so keeping it to what is irreducibly capability-bound
stays with the author. They bound the hole; they do not fill it.

## Enforcement

`--strict-markers` in `pyproject.toml` refuses any marker the registry
there does not declare, so a retired or misspelt marker fails collection
instead of selecting nothing.

`src/cadrumo/tests/test_every_test_module_is_lane_reachable.py` and
`dev/tests/test_lane_reachability.py` fail when a test is selected by no
lane.

The repo-root `conftest.py` invokes the collection policy in
`cadrumo.tests.marker_hook` once for every collected subtree. It raises
`pytest.UsageError` when a test item lacks exactly one execution marker or
exactly one accepted `hex_*` marker.

## Live Read Opt-In

`aeat_live` tests are excluded from the default test selection. When selected
explicitly, each live test fails at the shared prerequisite gate unless
`CADRUMO_LIVE_TESTS_ENABLED=1` is configured. The canonical setting name is
`CADRUMO_LIVE_TESTS_ENABLED`.

The opt-in is enforced at two layers:

1. `pyproject.toml` sets `addopts = "... -m 'unit' ..."` so plain local
   test runs select only unit tests.
2. `src/cadrumo/tests/live_gate.py` fails explicitly selected `aeat_live`
   tests when the required opt-in is absent; it never converts them into
   skipped tests.

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

Live tests must observe real external state. Snapshot/record, interception,
retry, and clock-control libraries are not part of the accepted test-control
surface.

## Plugin Roster

| plugin | scope | role | pitfalls |
| --- | --- | --- | --- |
| `pytest-asyncio` | unit + integration + live | async test collection (`asyncio_mode = "strict"`) | plain `async def` tests need an explicit async marker |
| `pytest-playwright` | live fixtures only | browser fixtures (`page`, `browser`, `context`); deterministic adapter-unit tests may launch the production Playwright session against local `data:` pages without these fixtures | needs `playwright install` for browser binaries |
| `pytest-xdist` | offline only | parallel deterministic suite | not safe for live tests |
| `pytest-cov` | unit only | coverage measurement and fail-under | live tests are excluded from the coverage lane |

## Coverage Gate

Starting threshold is 60% against `src/cadrumo`, enforced by the coverage
lane. Branch coverage is enabled. Test modules are omitted from
coverage through the `tests` topology and `test_*.py` file pattern.

Ratchet policy: the threshold only moves up. Lowering it requires a
documented rationale.

## Recipes

- `just test-unit` - unit suite (`-m 'unit'` via pyproject `addopts`).
- `uv run pytest -m integration` - deterministic cross-layer tests.
- `uv run pytest -m aeat_live` - live read-only tests; requires
  `CADRUMO_LIVE_TESTS_ENABLED=1`.
- `uv run pytest -m "unit and hex_domain"` - unit tests for the domain layer.
- `uv run pytest -m "integration and hex_entrypoint"` - CLI integration tests.
- `just test-coverage` - unit suite with coverage.
- `just test-resident-service` - resident-service retrieval contracts after an incremental reindex.
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
6. Do not use HTTP interception, snapshot/record, retry, or clock-control
   libraries as substitutes for real behaviour.
7. Run the relevant focused pytest lane before closing a change.

## Cross-References

- `src/cadrumo/tests/marker_hook.py` - shared collection hook body.
- `src/cadrumo/tests/test_marker_contract_enforcement.py` - proves the
  hook reports a violation both at `-n0` and under xdist workers.
- `src/cadrumo/tests/os_keychain_hook.py` - shared credential-store
  precondition for `os_keychain` cases.
- `dev/tests/test_lane_reachability.py` - per-test lane reachability gate.
- `pyproject.toml` - pytest discovery, marker registry, and coverage
  omit settings.
