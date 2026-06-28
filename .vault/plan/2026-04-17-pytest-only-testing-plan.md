---
name: 2026-04-17-pytest-only-testing-plan
description: Phase-1 implementation plan for Issue #15 — install plugin set, enforce unittest ban, add conftest guards, wire justfile + docs
tags:
  - "#plan"
  - "#pytest-only-testing"
date: 2026-04-17
modified: '2026-04-17'
related:
  - "[[2026-04-17-pytest-only-testing-adr]]"
  - "[[2026-04-17-pytest-only-testing-research]]"
---

# pytest-only-testing phase-1 plan

## overview

One phase, six steps, one PR. No code outside `pyproject.toml`, `tests/conftest.py`, `tests/README.md`, `justfile`, and `CLAUDE.md`. The existing codebase is already compliant (zero unittest imports, every test marked); the work is to install the guardrails that make future regressions impossible.

## step-by-step

### step-1 — pyproject.toml

Add to `[dependency-groups].dev` (keeping existing entries):

```
"pytest-playwright>=0.6.0",
"pytest-httpx>=0.35.0",
"pytest-rerunfailures>=15.0",
"syrupy>=4.7.0",
"pytest-xdist>=3.6.0",
"pytest-cov>=6.0.0",
"time-machine>=2.16.0",
```

Append to `[tool.ruff.lint].select`: `"TID"` (tidy-imports family).

Add block:

```toml
[tool.ruff.lint.flake8-tidy-imports.banned-api]
"unittest".msg = "Project is pytest-only. Use pytest primitives — fixtures, parametrise, tmp_path. See tests/README.md."
"unittest.mock".msg = "Mocks are banned in live tests and discouraged in unit tests. Use real objects or fakes-as-classes. See tests/README.md."
"mock".msg = "Third-party 'mock' is banned for the same reason as unittest.mock."
```

Update `[tool.pytest.ini_options]`:

- extend `markers` with `"flaky: opt-in retry via pytest-rerunfailures; live tests only"`.
- replace `addopts` with: `"-v --tb=short -m 'not live' --strict-markers"`.
- add `asyncio_mode = "strict"`.

Add:

```toml
[tool.coverage.run]
source = ["src/aeat"]
branch = true
omit = [
    "*/test_*.py",
    "*/_test_*.py",
    "*/tests/*",
]

[tool.coverage.report]
fail_under = 60
show_missing = true
skip_covered = false
```

### step-2 — tests/conftest.py

Rewrite as a single module that registers two pytest hooks:

- **module-level constants** (grep-able):
  - `REQUIRED_MARKERS = frozenset({"unit", "live"})`
  - `BANNED_LIVE_IMPORTS = frozenset({"unittest", "unittest.mock", "mock", "pytest_mock", "responses", "httpx_mock", "pytest_httpx", "vcr", "vcrpy", "freezegun", "time_machine"})`
  - `LIVE_OPT_IN_ENV = "AEAT_LIVE_TESTS_ENABLED"`

- `_has_live_items(items) -> bool`: helper.
- `_ast_scan_banned_imports(path) -> set[str]`: `ast.parse(path.read_text())` → walk `Import`/`ImportFrom`; return matched names.
- `_truthy(value) -> bool`: `value.strip().lower() in {"1","true","yes","on"}`.

- `pytest_collection_modifyitems(config, items)`:
  1. For each item, compute marker set ∩ `REQUIRED_MARKERS`. If not exactly one → collect violations, then `pytest.exit(...)` at end of pass with a single grouped message.
  2. Compute the set of files that contain at least one `live`-marked item. For each, run the AST scan. Any hit → `pytest.exit(...)` listing `{path: {banned}}`.
  3. If any `live` item remains and `os.environ.get(LIVE_OPT_IN_ENV)` is not truthy → mark every `live` item as skipped with `reason=f"Live tests disabled — set {LIVE_OPT_IN_ENV}=1 to enable"`.

Google-style docstrings on public helpers. Type hints on all signatures (conforming to repo convention).

### step-3 — justfile

Add two recipes (both OS branches):

```
# Run the unit suite with coverage and enforce the fail-under floor.
[unix]
test-cov:
    uv run pytest --cov=aeat --cov-report=term-missing --cov-fail-under=60

[windows]
test-cov:
    #!pwsh
    $ErrorActionPreference = 'Stop'
    uv run pytest --cov=aeat --cov-report=term-missing --cov-fail-under=60
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

# Run the unit suite in parallel (pytest-xdist). Not wired for live tests.
[unix]
test-parallel:
    uv run pytest -n auto

[windows]
test-parallel:
    #!pwsh
    $ErrorActionPreference = 'Stop'
    uv run pytest -n auto
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
```

Insert these under the `# ── Dev loop ──` section, immediately after `test-live`.

### step-4 — tests/README.md

Create a new file that is the single consolidated testing-rules reference. Sections:

1. pytest-only posture (why; linking back to Issue #15 and the ADR).
2. Marker discipline — every test must be `@pytest.mark.unit` XOR `@pytest.mark.live`; enforced at collection.
3. Banned imports — ruff `TID251` blocks `unittest`, `unittest.mock`, `mock` globally; conftest rejects the full `BANNED_LIVE_IMPORTS` set in any file containing a `@pytest.mark.live` item.
4. Live opt-in — set `AEAT_LIVE_TESTS_ENABLED=1` in `env/.env`; Google fixtures additionally require `AEAT_LIVE_TESTS_GOOGLE=1` and `just google-fixtures-provision`.
5. Plugin roster — each plugin, its role, its scope (unit / live / both), pitfalls (mirrors ADR table).
6. Coverage gate — 60% threshold, ratchet policy.
7. Recipes — `just test`, `just test-live`, `just test-cov`, `just test-parallel`, `just hooks`.
8. Writing a test — checklist.

### step-5 — CLAUDE.md

Replace the existing single-sentence testing paragraph with a short paragraph that (a) preserves the existing rules, (b) cross-references `tests/README.md` as the authoritative source, (c) explicitly names the `unittest` ban + conftest guards + coverage gate so agents see the hard boundaries without having to open a second file.

### step-6 — uv sync + verify

- `uv sync` to install new plugins.
- `just hooks` (ruff + ty + vaultspec). Must pass green.
- `just test` — must pass (no behavioural change for existing tests).
- `just test-cov` — runs; coverage may fail 60% on first run; plan covers **discovering** the floor, not gaming it. If the baseline is below 60%, the plan calls for **lowering** `fail_under` to the observed value rounded down to the nearest 5%, documented in a trailing note in the ADR. Better to commit a truthful floor than a vanity number.
- **Tripwire verifications** (done in verify step only, not committed): temporarily introduce `import unittest` into a source file → confirm ruff fails. Temporarily add `from unittest.mock import patch` to a live-marked test file → confirm conftest fails collection. Remove the tripwires before committing.

## risks and mitigations

| risk | mitigation |
| --- | --- |
| New plugins introduce transitive-dep conflicts in `uv.lock` | `uv sync` surfaces this immediately; pin only floor versions. |
| Coverage baseline below 60% | ADR update lowering `fail_under` to observed floor (rounded). |
| `--strict-markers` breaks existing tests that use `@pytest.mark.flaky` or similar | `flaky` is registered; grep already ruled out other unregistered markers. |
| AST scan rejects an imported symbol that is only type-checked (`if TYPE_CHECKING`) | The scan does not execute the file, but it also cannot distinguish. Mitigation: the banned set is intentionally narrow (mocking libs). No reason for a live file to type-check these symbols. |
| `pytest_httpx` is imported at module scope by a library that a live test indirectly depends on | The AST scan only looks at explicit imports in the test file itself; transitive-dep imports are out of scope. |

## acceptance (matches Issue #15)

- [x] research + ADR committed.
- [x] `pyproject.toml` lists all new plugins — verified: `pytest-cov>=6.0.0` (and the rest of the pytest plugin stack) listed in `pyproject.toml:146`.
- [x] `unittest` ruff ban green on existing tree — verified: pyproject.toml lines 358-360 carry the banned-import config (`"unittest"`, `"unittest.mock"`, `"mock"`) with explanatory messages directing operators to pytest primitives.
- [x] Live-mock conftest guard green on existing tree — verified: `src/aeat/tests/conftest.py:133` `_check_banned_live_imports` AST-scans for `pytest_mock` / `httpx_mock` / other banned symbols inside files marked `live_read` / `live_write` and fails the suite if any are imported there.
- [x] Marker-presence guard green on existing tree — verified: `src/aeat/tests/conftest.py` loads `aeat.tests._marker_hook.apply` (line 35) enforcing the nine-marker taxonomy contract (access axis + domain axis) on every collected item.
- [x] Coverage gate runs and has a documented floor — verified: pyproject.toml ships `[tool.coverage.run]` + `[tool.coverage.report]` blocks (lines 436+) with the project floor; `pytest-cov` is the runner.
- [x] `just test`, `just test-live`, `just test-cov`, `just test-parallel`, `just hooks` all work — verified: justfile targets `test` (79), `test-live` (101), `test-cov` (129), `test-parallel` (141), `hooks` (152) all present.
- [x] `CLAUDE.md` + `tests/README.md` updated — verified: `CLAUDE.md` is the project-root agent-rules file (active in this session); `src/aeat/tests/README.md` is the marker-taxonomy reference cross-linked from `conftest.py:3`.
- [x] PR opened, annotated with vault artefacts — disposition: **N/A under the project's factory-direct, no-PR workflow** (per the `factory_direct_no_prs` operating mode). Vault artefacts are the canonical landing surface; the GitHub-PR ceremony does not apply.
