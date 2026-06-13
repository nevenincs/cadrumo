---
name: 2026-04-17-pytest-only-testing-adr
description: Lock the project into a pytest-only testing posture with an enforced unittest ban, a live-mock-import guard, marker discipline, and a documented plugin set for live-web integration
tags:
  - "#adr"
  - "#pytest-only-testing"
date: 2026-04-17
modified: '2026-04-17'
related:
  - "[[2026-04-17-pytest-only-testing-research]]"
  - "[[2026-04-12-dev-scaffolding-adr]]"
  - "[[2026-04-12-base-module-structure-adr]]"
  - "[[2026-04-16-live-write-test-audit-adr]]"
status: accepted
---

# pytest-only-testing adr

## status

accepted — 2026-04-17

## context

CLAUDE.md already mandates pytest with marker-gated unit/live tests and forbids mocks in live tests. The mandate is declarative only: nothing enforces it at commit- or collection-time. A contributor (human or agent) can silently import `unittest.mock` or `pytest_mock` into a live test and violate the live-AEAT-write safety charter (memory: live_write_safety). Issue #15 closes that gap.

This ADR decides the plugin set, the enforcement surface, and the opt-in gating.

## decision

### 1 — plugin set added to `[dependency-groups].dev`

Every plugin must solve a concrete, near-term problem. The following are accepted:

| plugin | role | scope | rationale |
| --- | --- | --- | --- |
| `pytest-asyncio` | async test collection | unit + live | Playwright path is async-first; already installed. Pin `asyncio_mode = "strict"` so plain coroutines are not collected by accident. |
| `pytest-playwright` | browser fixtures for live AEAT flow tests | live only | `aeat.adapters.outbound.aeat.browser` needs a standardised harness; complements the MCP Playwright path. |
| `pytest-httpx` | httpx wire-shape assertions | unit only | AEAT integrations ride httpx; unit tests must assert URL / headers / body without hitting the network. Must be a **banned import** in any `@pytest.mark.live` file. |
| `pytest-rerunfailures` | retry flaky live endpoints | live only, per-test opt-in via `@pytest.mark.flaky(reruns=N)` | AEAT has real maintenance windows; scoped retries prevent environmental flake from masking commits. **Never** applied globally and **never** to unit tests. |
| `syrupy` | snapshot diffing | both | #7 casilla extractions and #9 modelo schemas produce large structured output. |
| `pytest-xdist` | parallel unit suite | unit only, **opt-in** via a new `just test-parallel` recipe | ~880 tests today; xdist-by-default would mask fixture-scope bugs and break the live suite's ordering guarantees. |
| `pytest-cov` | coverage measurement + floor | unit only | documented minimum (see 5 below). Live suite excluded from coverage. |
| `time-machine` | wall-clock control | unit only | deadline engine (#10), expedientes parsers compute against wall time. C-extension implementation is faster and more correct than `freezegun`. Banned in live tests. |

Explicitly **not adopted**:

- `pytest-sugar`, `pytest-rich` — quality-of-life noise; built-in output is adequate.
- `pytest-github-actions-annotate-failures` — GitHub Actions is permanently disabled on this repo (memory: github_actions_disabled).
- `freezegun` — `time-machine` supersedes it.
- `pytest-timeout` — no concrete flake yet. Add only when it hits us.

### 2 — enforce the unittest ban via ruff `TID251`

Add `[tool.ruff.lint.flake8-tidy-imports.banned-api]` with entries for `unittest`, `unittest.mock`, and third-party `mock`. Ruff rejects the import at lint-time (`just lint`) and at the pre-commit hook (`prek`). The codebase is already clean (grep confirms zero real imports; existing hits are narrative mentions in docstrings/comments, none of which are actual imports). The rule must be green on the existing tree from day one.

The `TID` rule family is added to `[tool.ruff.lint].select`.

### 3 — conftest-driven collection guards

A single `tests/conftest.py` `pytest_collection_modifyitems` hook implements three invariants:

1. **Marker presence**: every collected item has exactly one of `unit` / `live`. Missing → fail collection. Both → fail collection.
2. **Live-file mock-import scan**: for any file containing at least one `live`-marked item, AST-parse the file and reject the session if it imports any symbol from the banned set:
   ```
   {"unittest", "unittest.mock", "mock", "pytest_mock",
    "responses", "httpx_mock", "pytest_httpx", "vcr", "vcrpy",
    "freezegun", "time_machine"}
   ```
   `pytest_httpx`, `freezegun`, and `time_machine` are unit-only by ADR and must not appear in a live file even if installed. AST-based scan; never execute the file.
3. **Live opt-in gate**: when any collected item is marked `live`, the hook checks `AEAT_LIVE_TESTS_ENABLED`. If unset/false, the entire live subset is skipped with a single, clear reason string. Individual tests are not silently skipped.

Collection-time failure surface = hard, single-line `pytest.exit(..., returncode=2)` with the offending file and symbol. `pytest.exit` (not `pytest.fail`) is the correct primitive here because the violations are session-wide — a single malformed live file taints the whole collection. No warnings, no "--strict" flag required.

### 4 — marker configuration

Register a third documented marker `flaky` so `@pytest.mark.flaky(reruns=N)` does not trigger `--strict-markers`:

```toml
markers = [
    "unit: deterministic tests with no external I/O",
    "live: tests that hit real AEAT/Google/external endpoints",
    "flaky: opt-in retry via pytest-rerunfailures; live tests only",
]
```

`--strict-markers` is **added** to `addopts` so an unregistered marker is a hard error.

### 5 — coverage gate

Starting threshold **60%**, enforced only on the unit suite. Rationale: the repository has never been measured; 80% is aspirational without evidence. 60% is the minimum floor that prevents brand-new code from shipping without tests. The ADR mandates ratcheting up in follow-up ADRs once the baseline is measured. Live suite is excluded from coverage via `--cov` scope and the `-m "not live"` filter in the cov recipe.

Coverage config lives in `pyproject.toml` under `[tool.coverage.run]` (`source = ["src/aeat"]`, `branch = true`) and `[tool.coverage.report]` (`fail_under = 60`, `skip_covered = false`, `show_missing = true`).

### 6 — justfile recipes

- `just test` — unchanged behaviour (`uv run pytest`, skips live).
- `just test-live` — unchanged (`uv run pytest -m live`).
- `just test-cov` — **new**: `uv run pytest --cov=aeat --cov-report=term-missing --cov-fail-under=60`.
- `just test-parallel` — **new**: `uv run pytest -n auto` (unit suite only; xdist never on live).

Windows + Unix variants follow the existing pattern (both shell branches already tested and present).

### 7 — documentation

- `CLAUDE.md` testing paragraph expanded to reference the full enforcement set and the new `tests/README.md`.
- `tests/README.md` created as the single consolidated reference: marker rules, banned imports (source + live), opt-in env vars, coverage gate, justfile recipes, plugin roster with scope notes. One authoritative document — not duplicated across README.md and CLAUDE.md.

## consequences

### positive

- A contributor cannot accidentally sneak a mock into a live test: ruff rejects it in source, conftest rejects it at collection, and the live suite is the only surface that would even exercise it.
- Marker discipline is enforced at the entrypoint, not at review time.
- Coverage has a measurable floor that can only move up.
- Plugin set is **minimal**: each plugin has a documented role and scope.

### negative / pitfalls

- Adding `pytest-rerunfailures` creates a risk that a flaky live test masks a real bug. Mitigation: marker is **opt-in per-test**, not global.
- `pytest-xdist` surfaces fixture-scope bugs that were latent in the serial suite. Mitigation: opt-in recipe, not default.
- Coverage at 60% will feel low; the ratchet lives in a follow-up ADR that consumes the first measured baseline.
- The conftest AST scan has a one-time cost at collection. Negligible at 1k tests; monitor if the suite grows 10×.

### risks neutralised

- Live-AEAT-write safety charter (memory: live_write_safety): a test importing `unittest.mock` into a live file can no longer silently pass. Both ruff and conftest block it.
- Drift between "what CLAUDE.md says" and "what the suite enforces" is eliminated — the rules are executable.

## alternatives considered

- **Add `unittest` ban via a bespoke prek hook** — rejected. Ruff already traverses imports; a second scanner duplicates work and complicates the pre-commit config.
- **Use `pytest-mock` as the "blessed" mock lib for unit tests** — rejected. The project's culture (memory: pydantic_mandate + live_write_safety) is to prefer real objects / fakes-as-classes. Permitting `pytest-mock` reopens the door `unittest.mock` is trying to close.
- **Coverage threshold 80%** — rejected as starting point (no baseline yet). Will revisit after first measurement.
- **xdist-by-default** — rejected. The suite has shared fixture mutations (e.g. `tests/conftest.py` scope changes coming in #7/#9) that have not been audited for parallel safety.

## implementation pointers

- `pyproject.toml`:
  - extend `[dependency-groups].dev` with the eight plugins above.
  - add `TID` to `[tool.ruff.lint].select`.
  - add `[tool.ruff.lint.flake8-tidy-imports.banned-api]`.
  - extend `markers` with `flaky`; add `--strict-markers` + `asyncio_mode = "strict"` to pytest config.
  - add `[tool.coverage.run]` + `[tool.coverage.report]`.
- `tests/conftest.py`:
  - `pytest_collection_modifyitems` hook implementing marker-discipline + live-mock AST scan + live opt-in gate.
  - Banned set + marker names sourced from module-level constants so the list is grep-able.
- `justfile`: add `test-cov` and `test-parallel` (unix + windows variants).
- `CLAUDE.md`: expand the testing paragraph to cross-reference `tests/README.md`.
- `tests/README.md`: new, authoritative.

## decision review

This ADR is self-audited against Issue #15's acceptance list:

- [x] Vault research artefact + ADR enumerating chosen plugins with justifications.
- [x] `pyproject.toml` updates defined for every plugin under a group.
- [x] `unittest` / `unittest.mock` import ban via ruff `TID251`, *and* a conftest guard that additionally scans live files for the broader banned set (belt-and-braces).
- [x] Live-test mock-import ban enforced by collection-time guard.
- [x] Marker-presence guard enforced.
- [x] Coverage gate wired and documented (60% starting threshold).
- [x] Justfile recipes covered (`test`, `test-live`, `test-cov`, `test-parallel`).
- [x] Documentation: CLAUDE.md + new `tests/README.md`.

Non-negotiables met: pytest-only, no unittest, no mocks in live tests, every test marked, live tests opt-in via `AEAT_LIVE_TESTS_ENABLED`.
