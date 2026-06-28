---
name: 2026-04-17-pytest-only-testing-research
description: Survey of current testing posture and plugin-set options for Issue #15 (pytest-only lockdown, unittest ban, live-web integration plugins)
tags:
  - "#research"
  - "#pytest-only-testing"
date: 2026-04-17
modified: '2026-04-17'
related:
  - "[[2026-04-12-base-module-structure-adr]]"
  - "[[2026-04-12-dev-scaffolding-adr]]"
  - "[[2026-04-16-live-write-test-audit-adr]]"
  - "[[2026-04-12-google-fixtures-adr]]"
---

# pytest-only-testing research

## context

Issue #15 locks the project into a **pytest-only** testing posture with three non-negotiables:

1. pytest is the sole test runner; `unittest` / `unittest.mock` imports are forbidden anywhere in the tree.
2. Tests marked `@pytest.mark.live` must not import any mocking / recording / replay library.
3. Every test must carry exactly one of `@pytest.mark.unit` or `@pytest.mark.live` — no default, missing is an error.

This research surveys the current configuration, inventories the candidate plugin set, and identifies the smallest change that achieves the mandate without over-reach.

## current state

### pyproject.toml

- `[dependency-groups].dev` already includes `pytest>=9.0.3`, `pytest-asyncio>=1.0.0`, `playwright>=1.58.0`, `playwright-stealth>=2.0.3`, `reportlab>=4.4.10` (fixture generator), plus `ruff`, `ty`, `prek`.
- `[tool.pytest.ini_options]` registers both markers (`unit`, `live`) and sets `addopts = "-v --tb=short -m 'not live'"` — live tests are already skipped by default.
- `[tool.ruff.lint].select` covers E/W/F/I/N/UP/B/S/T20/SIM/RUF. No banned-imports rule (`TID251`) is configured.
- `testpaths = ["src", "tests"]`; `python_files = ["test_*.py", "_test_*.py"]`.

### justfile

- `just test` → `uv run pytest` (skips live via `addopts`).
- `just test-live` → `uv run pytest -m live`.
- No `just test-cov` recipe yet.
- `just hooks` runs `prek run --all-files`; `prek.toml` wires ruff + ty, `.pre-commit-config.yaml` adds vaultspec hooks.

### conftest.py

- `tests/conftest.py` is a one-line placeholder. There is **no** collection-time marker guard, **no** live-mock import scan, and **no** live opt-in gate via conftest (the `addopts` filter is the only gate).

### existing test corpus

- 910 tests collect cleanly (24 deselected live). Grep shows **zero** actual `unittest` or `unittest.mock` imports in `src/` or `tests/`. No `pytest_mock`, `responses`, `httpx_mock`, `vcr`, or `freezegun` usage. Mentions of "unittest" in code are narrative docstring references only.
- Every test file sampled uses either `@pytest.mark.unit` or `@pytest.mark.live` today. The audit will still add a collection-time guard so regressions are caught at the entrypoint rather than at review.

### env vars (authoritative)

- `src/aeat/config.py` defines `aeat_live_tests_enabled` and `aeat_live_tests_google` on the pydantic `Settings` model; `env/.env.example` documents them. The canonical env var is **`AEAT_LIVE_TESTS_ENABLED`** (not `AEAT_LIVE_TESTS`). The issue text uses the shorter form illustratively; the established name is the long form and must be preserved. (Memory: "live_test_env_var".)

## candidate plugins (matched to concrete problems)

For each plugin, the research records: **what** it does, **why** this project will hit the problem, **where** it is allowed, and **pitfalls**.

### async — `pytest-asyncio` (already installed)

- **What:** collects and runs `async def` tests. Built-in for pytest.
- **Why:** the `aeat.adapters.outbound.aeat.browser` Playwright path is async-first; async tests already exist in `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/`.
- **Where:** both unit and live.
- **Pitfalls:** `asyncio_mode` must be pinned (`strict` recommended) to avoid accidental auto-collection of plain coroutines.

### live HTTP / browser — `pytest-playwright`

- **What:** Playwright's official pytest plugin. Provides `page`, `browser`, `context` fixtures and CLI flags (`--headed`, `--browser`, `--tracing`).
- **Why:** `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/test_live_evasion.py` and future AEAT flow tests need a standardised browser harness. The project already pins `playwright>=1.58.0` as a runtime dep; the pytest plugin is additive.
- **Where:** live only (browser sessions consume quota; unit tests must remain hermetic).
- **Pitfalls:** plugin pulls its own browser download step (`playwright install`). Not a problem since we already document it.

### unit HTTP wire-shape — `pytest-httpx`

- **What:** transport-level httpx mock for unit tests that need to assert *request wire shape* (URL, headers, body) without hitting the network.
- **Why:** AEAT integrations are over httpx (e.g. `src/aeat/status/`, `src/aeat/aeat/`). Wire-shape tests catch URL / header regressions deterministically.
- **Where:** **unit only.** Collision with the live-mocks ban must be enforced: `pytest-httpx` counts as a banned import in any `@pytest.mark.live` file.
- **Pitfalls:** easy to reach for on a live test when an integration is flaky — that's the exact failure mode the live-mock guard exists to prevent.

### retries on intermittent live endpoints — `pytest-rerunfailures`

- **What:** re-runs failed tests up to N times with optional backoff.
- **Why:** AEAT's own infrastructure has intermittent maintenance windows; without scoped retries, real bugs get masked by environmental flake.
- **Where:** **live only**, opt-in per-test via `@pytest.mark.flaky(reruns=N)` — never globally. Unit tests must be deterministic; a rerun there is a bug-mask.
- **Pitfalls:** mis-applied globally would hide genuine regressions. The ADR must mandate opt-in at the individual-test level.

### snapshots — `syrupy`

- **What:** snapshot diffing; stores and diffs serialised output against committed baselines.
- **Why:** #9 (modelo schemas) and #7 (casilla extractions) will produce large structured output where a diff-based baseline is cheaper than hand-written assertions.
- **Where:** both.
- **Pitfalls:** snapshot rot — rules of thumb: never `--snapshot-update` in CI; review diffs like code.

### parallelism — `pytest-xdist`

- **What:** parallel test execution across workers.
- **Why:** the unit suite is large (~880 tests) and will grow; xdist scales locally.
- **Where:** **unit only.** Live tests frequently have rate-limit, ordering, or quota coupling; parallelism breaks them silently.
- **Pitfalls:** fixture scope (`session` / `module`) changes behaviour under xdist — tests that mutate shared state need `--dist loadfile` or per-worker isolation.

### coverage — `pytest-cov`

- **What:** integrates coverage.py with pytest, produces term/XML/HTML reports and a failure threshold via `--cov-fail-under`.
- **Why:** a measurable unit-suite floor keeps regressions honest.
- **Where:** **unit only.** Live tests exercise real external systems and should not inflate the coverage metric.
- **Pitfalls:** gaming the metric. Threshold needs pragmatic starting value — recommend **60%** not 80% on the first pass; the codebase has large pure-typer CLI surfaces that are legitimately unit-tested via a different route, and the current coverage baseline has never been measured. Per issue guidance: "revisit per ADR". Start low, ratchet up.

### time control — `time-machine`

- **What:** monkey-patches `datetime.now()`, `time.time()` with microsecond-accurate shifting; C-extension, faster + more correct than `freezegun`.
- **Why:** deadline engine (#10), expedientes parsers, and reconciliation code all compute against wall time. Unit tests must exercise month-end / year-end boundaries deterministically.
- **Where:** **unit only.** Live tests never freeze time — they observe real AEAT clocks.
- **Pitfalls:** forgetting to restore the clock across async boundaries. Use the `travel()` context manager, not module-level monkeypatches.

### reporting — (defer)

- `pytest-rich` and `pytest-sugar`: quality-of-life; **not added**. Sugar clutters CI logs; built-in `--tb=short` output is enough for a local-only project.
- `pytest-github-actions-annotate-failures`: **not added**. The repository has GitHub Actions **permanently disabled** (memory: github_actions_disabled); there is no CI to annotate.

## enforcement mechanisms

Three enforcement surfaces are needed. Each one has a clear tool.

### unittest / unittest.mock ban — ruff `TID251`

`tidy-imports` (`TID251`) rejects banned imports with a configurable message. Single config block in `pyproject.toml`:

```toml
[tool.ruff.lint.flake8-tidy-imports.banned-api]
"unittest".msg = "Project is pytest-only. Use pytest primitives (fixtures, parametrise, tmp_path)."
"unittest.mock".msg = "Mocks are banned in live tests and discouraged in unit tests. Use real objects / fakes-as-classes."
"mock".msg = "Third-party 'mock' is banned. Use real objects or pytest fixtures."
```

Ruff enforces at commit-time (via prek/ruff hook) and locally (`just lint`). Zero runtime cost.

### live-test mock-import guard — pytest collection hook

A `pytest_collection_modifyitems` hook in `tests/conftest.py` scans every file that contains any item marked `@pytest.mark.live` for AST-level imports of the banned set:

```
{"unittest", "unittest.mock", "mock", "pytest_mock",
 "responses", "httpx_mock", "pytest_httpx", "vcr", "vcrpy"}
```

Failure mode: `pytest.fail(...)` at collection time with the offending file + banned symbol — **not** a warning, not a skip. AST-based so we do not execute imports while scanning.

### marker discipline — pytest collection hook

Same hook layer; second pass. Every collected item must have exactly one of `unit` / `live`. Missing marker → `pytest.fail()`. Both markers → `pytest.fail()`. This makes "forgot the marker" a hard error at the entrypoint.

### live opt-in — already wired via `addopts = "-m 'not live'"`

The `-m 'not live'` filter in `pyproject.toml` already gates live tests. The ADR should add a belt-and-braces layer: even when selected by `-m live`, the conftest hook checks `AEAT_LIVE_TESTS_ENABLED` env var and skips the session (not individual tests) with a clear reason if unset. This matches `src/aeat/config.py` and every handover prompt the PM issues.

## scope boundary

Explicitly **out of scope** for this issue:

- Raising the coverage threshold beyond the starting line — that is a follow-up once the baseline is measured.
- CI wiring — GitHub Actions is permanently disabled for this repo.
- Writing actual tests for #6/#7/#8/#9/#10/#11.
- Adding `pytest-sugar` / `pytest-rich` / `freezegun` / `pytest-timeout`. None solve a concrete problem today.

## open questions for the ADR

1. Coverage starting threshold: **60%** (recommended) vs **80%** (issue suggestion) vs **0% + baseline-only**.
2. `asyncio_mode`: `strict` (recommended, explicit per-test opt-in via marker) vs `auto`.
3. Should `pytest-xdist` be **on by default** in `just test` (e.g. `-n auto`) or opt-in via `just test-parallel`? Xdist-by-default hides fixture-scope bugs.

The ADR decides each one and records the rationale.
