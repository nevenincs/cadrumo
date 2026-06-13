---
tags:
  - "#plan"
  - "#pytest-markers"
date: 2026-04-17
modified: '2026-04-17'
related:
  - "[[2026-04-17-pytest-markers-adr]]"
  - "[[2026-04-17-pytest-markers-research]]"
  - "[[2026-04-16-live-write-test-audit-adr]]"
  - "[[2026-04-12-submission-engine-adr]]"
  - "[[2026-04-13-filing-complementaria-adr]]"
  - "[[2026-04-12-base-module-structure-adr]]"
---



# `pytest-markers` `phase-1` plan

Deliver issue `#163` as a single-branch, test-infrastructure-only refactor that promotes the pytest marker vocabulary from the binary `unit | live` pair to a nine-marker access+domain taxonomy, replaces the boolean live marker with `live_read` / `live_write`, installs a three-factor collection-time ban for `live_write`, and migrates every existing test module to module-level `pytestmark` declarations. The feature ships dormant live-write infrastructure: zero `live_write` tests exist today and none are added here. Charter `#116` rules `R1`..`R6` are left verbatim; the new collection hook layers additive defence in depth on top of `SubmissionEngine` runtime refusal (`R5`) and the `AEAT_LIVE_SUBMIT_ENABLED` env gate (`R3`).

## Proposed Changes

- Replace the two-entry `markers` table in `pyproject.toml` with the nine-entry ADR taxonomy and update `addopts` to `-v --tb=short -m 'unit'`.
- Add a `pytest_collection_modifyitems` hook with the three-factor `live_write` bypass, drop-not-skip semantics, and missing-marker `UsageError` raises. A planning-time probe (recorded below in `Planning-time probe: hook reach`) has established that `tests/conftest.py` does NOT fire for items collected under `src/aeat/...` on this repo layout; the hook is therefore implemented in a shared helper and invoked from BOTH a new repo-root `conftest.py` (for `src/aeat/` collection) AND `tests/conftest.py` (for `tests/` collection). This makes phase 3 commits deterministic and honours research gotcha 6.
- Add `tests/test_marker_integrity.py` as an AST-backed unit test that walks every test module under `src/aeat/` and `tests/` and rejects any module missing exactly one access marker or at least one domain marker applied at module level.
- Migrate every existing `test_*.py` and `_test_*.py` module (approximately 140 files; 14 currently `live`-marked, 126 currently `unit`-marked) to module-level `pytestmark = [pytest.mark.<access>, pytest.mark.<domain>]`. Strip per-function `@pytest.mark.unit` and `@pytest.mark.live` decorators. Rename any remaining `@pytest.mark.live` function references to `live_read`.
- Split any module that mixes `unit` and `live_read` test functions into two modules before applying markers (zero such modules have been identified in the research survey, but the integrity test will surface any that the survey missed).
- Add `aeat_live_write_unsafe_bypass: bool = Field(default=False, description=...)` and `aeat_live_write_unsafe_bypass_confirm: str = Field(default="", description=...)` to `aeat.core.config.Settings` with loud warning text supplied in the `description=` kwarg (NOT as Python docstrings or comments), mirror both lines in `env/.env.example`, and keep `tests/test_config.py` green. `tests/test_config.py` enforces alignment against `Field(description=...)`; inline Python docstrings do not satisfy the invariant.
- Rewrite the `justfile` `test` and `test-live` recipes, add `test-live-read`, `test-domain DOMAIN`, and add `test-live-write` as a documentation surface for the three-factor bypass.
- Update `CLAUDE.md` testing paragraph to describe the new axes and the module-level mandate; add `tests/README.md` documenting the nine markers, the bypass phrase verbatim, and the cross-reference to charter `#116`.

## Planning-time probe: hook reach

During plan authoring the two candidate hook locations were probed directly to remove ambiguity from phase 3:

- Probe A: placed a `pytest_collection_modifyitems` that raises `RuntimeError("CONFTEST HOOK REACHED")` into `tests/conftest.py`, then ran `uv run pytest --collect-only -q src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/test_smoke.py`. Result: collection succeeded, NO `RuntimeError` surfaced. The hook is not reached for items collected under `src/aeat/...`.
- Probe B: placed the same probe into a repo-root `conftest.py`, reran the same command. Result: pytest internal error with the expected `RuntimeError` in the traceback. The hook IS reached for `src/aeat/...` items from a repo-root conftest.

Deterministic conclusion: the canonical hook host is a new repo-root `conftest.py`. `tests/conftest.py` still exists for per-subtree fixtures but also imports and invokes the shared hook helper for completeness. Step 2.4 becomes a confirmatory re-run rather than a branching decision.

## Scope Guardrails

- **No production-code changes under `src/aeat/*`** except the two additive `Settings` fields in `src/aeat/config.py`. A new test-infrastructure-only repo-root `conftest.py` at `Y:/code/aeat-worktrees/feature-163-pytest-markers/conftest.py` hosts the collection hook (NOT under `src/aeat/`; it sits at repo root). A new test-infrastructure-only shared helper at `tests/_marker_hook.py` holds the hook body. The planning-time probe above confirms no `src/aeat/conftest.py` is needed and none is created. Every other file under `src/aeat/` touched by this plan is a `test_*.py` / `_test_*.py` module; only markers and module structure change, never test function bodies.
- **Charter `#116` `R3` and `R5` are untouched.** `AEAT_LIVE_SUBMIT_ENABLED` remains the sole env gate for live submission; `SubmissionEngine.__init__` runtime refusal remains the last-line defence. The `live_write` bypass env vars are distinct and only control pytest collection.
- **No `live_write` tests are created.** The marker, the bypass, and the documentation are dormant infrastructure.
- **Test bodies are not modified.** Function-level parametrize decorators, fixtures, imports, and assertions remain byte-for-byte identical.
- **GitHub Actions is disabled on this repo.** No `.github/workflows/*` file is created or altered; `tests/test_release_config.py` enforces this invariant.

## Tasks


- `Phase 1: marker registration`
  1. `Step 1.1: rewrite pyproject.toml marker table and addopts`
- `Phase 2: collection hook + integrity test`
  1. `Step 2.1: add Settings fields and mirror env/.env.example`
  2. `Step 2.2: implement pytest_collection_modifyitems (shared helper + root + tests conftests)`
  3. `Step 2.3: add tests/test_marker_integrity.py AST walker`
  4. `Step 2.4: confirm hook reach from src/aeat/ collection root (confirmatory)`
- `Phase 3: migrate every test module to module-level pytestmark`
  1. `Step 3.1: migrate domain_aeat_remote test modules`
  2. `Step 3.2: migrate domain_submission test modules`
  3. `Step 3.3: migrate domain_financial_input test modules`
  4. `Step 3.4: migrate domain_local_state test modules`
  5. `Step 3.5: migrate domain_mediation test modules`
  6. `Step 3.6: migrate domain_infra test modules`
- `Phase 4: justfile recipes`
  1. `Step 4.1: rewrite test, test-live; add test-live-read, test-domain, test-live-write`
- `Phase 5: docs + env.example`
  1. `Step 5.1: update CLAUDE.md testing paragraph`
  2. `Step 5.2: create tests/README.md`
- `Phase 6: verification`
  1. `Step 6.1: run the full verification matrix`

---

## Phase 1: marker registration

### Step 1.1: rewrite pyproject.toml marker table and addopts

- Name: rewrite pyproject.toml marker table and addopts
- Step summary: `.vault/exec/2026-04-17-pytest-markers/2026-04-17-pytest-markers-phase-1-step-1.md`
- Executing agent: `vaultspec-standard-executor`
- References: `[[2026-04-17-pytest-markers-adr]]` sections `Marker registration` and `Axis A`/`Axis B`; `[[2026-04-17-pytest-markers-research]]` section 6

Description:

- Replace the two-entry `markers` list under `[tool.pytest.ini_options]` with the exact nine-entry taxonomy below (one line per marker; Google-scratch qualifier included in `live_read` description so the research gotcha is documented in-source):
  - `unit`: deterministic tests with no external I/O; mocks/stubs permitted per `CLAUDE.md`
  - `live_read`: opt-in tests that READ from a real external service (covers Google scratch round-trips; see tests/README.md)
  - `live_write`: opt-in tests that WRITE to a real external service; collection-banned by default (charter #116 R1)
  - `domain_aeat_remote`: exercises AEAT Sede Electronica read paths (auth, browser, casillas, inbox, justificante, portals, status, sync)
  - `domain_submission`: exercises the AEAT-write-capable submission boundary (filing, submission)
  - `domain_financial_input`: exercises financial ingest (financial, cli/financial)
  - `domain_local_state`: exercises on-disk catalogues and local SQLite mirror (storage, models, normatives, manuals, corpus, schema, deadlines, cli/deadlines)
  - `domain_mediation`: exercises workflow orchestration, LLM, i18n, testing subpackages
  - `domain_infra`: exercises project plumbing (root modules, non-domain cli, setup, top-level tests/*.py)
- Change `addopts = "-v --tb=short -m 'not live'"` to `addopts = "-v --tb=short -m 'unit'"`.
- Remove the stale `live` marker entry in the same commit as the hook and the file-level migration (the removal MUST be coincident with phase 3 completion to avoid `PytestUnknownMarkWarning` during the migration commit; in practice this is done as a single atomic commit covering phases 1-3).

Files touched:

- `Y:/code/aeat-worktrees/feature-163-pytest-markers/pyproject.toml`

Dependencies: none.

Verification commands:

- `uv run pytest --collect-only -q 2>&1 | grep -i "PytestUnknownMarkWarning"` must return empty after phase 3 completes.
- `grep -n "live_write\|domain_" pyproject.toml` confirms all nine markers registered.

Rollback: `git checkout -- pyproject.toml` restores the prior marker table; no runtime state change.

---

## Phase 2: collection hook + integrity test

### Step 2.1: add Settings fields and mirror env/.env.example

- Name: add Settings fields and mirror env/.env.example
- Step summary: `.vault/exec/2026-04-17-pytest-markers/2026-04-17-pytest-markers-phase-2-step-1.md`
- Executing agent: `vaultspec-standard-executor`
- References: `[[2026-04-17-pytest-markers-adr]]` section `Implementation`; `CLAUDE.md` env-alignment invariant; `tests/test_config.py`

Description:

- Add two pydantic-settings fields to `aeat.core.config.Settings`, following the existing project convention of `pydantic.Field(default=..., description=...)` used by every neighbouring field (for example `aeat_storage_auto_migrate`, `aeat_live_tests_enabled`, `aeat_casillas_review_required`). The warning text lives in the `description=` kwarg, NOT as a Python docstring or an inline comment; `tests/test_config.py` enforces alignment against `Field(description=...)` and `.env.example` mirrors the same copy.
  - `aeat_live_write_unsafe_bypass: bool = Field(default=False, description="UNSAFE. Pytest collection bypass factor 1 of 3 for @pytest.mark.live_write tests. NEVER set outside an interactive live-filing session. See charter #116.")`
  - `aeat_live_write_unsafe_bypass_confirm: str = Field(default="", description="UNSAFE. Pytest collection bypass factor 2 of 3. Must equal the phrase: I ACCEPT THE RISK OF FILING A LIVE TAX RETURN. NEVER set outside an interactive live-filing session.")`
- Mirror both in `env/.env.example` under a new `-- Live-write bypass (charter #116 R1) --` section using the same warning copy that appears in `description=`, plus an explicit "never set in CI or cron" line so the operator-facing surface matches the programmatic surface byte-for-byte where possible.
- Do NOT touch `AEAT_LIVE_SUBMIT_ENABLED`; leave its section intact.

Files touched:

- `Y:/code/aeat-worktrees/feature-163-pytest-markers/src/aeat/config.py`
- `Y:/code/aeat-worktrees/feature-163-pytest-markers/env/.env.example`

Dependencies: none.

Verification commands:

- `uv run pytest tests/test_config.py -m unit` must pass (enforces env-alignment invariant).
- `grep -n "AEAT_LIVE_WRITE_UNSAFE_BYPASS" env/.env.example src/aeat/config.py` shows both sides present.

Rollback: `git checkout -- src/aeat/config.py env/.env.example` reverts cleanly.

---

### Step 2.2: implement pytest_collection_modifyitems (shared helper + root + tests conftests)

- Name: implement pytest_collection_modifyitems (shared helper + root + tests conftests)
- Step summary: `.vault/exec/2026-04-17-pytest-markers/2026-04-17-pytest-markers-phase-2-step-2.md`
- Executing agent: `vaultspec-high-executor`
- References: `[[2026-04-17-pytest-markers-adr]]` section `Three-factor live_write bypass` and `Collection-time enforcement`; `[[2026-04-17-pytest-markers-research]]` section 5.2 (hook source sketch); planning-time probe above

Description:

- Create a shared helper module `tests/_marker_hook.py` (test-infrastructure, not a production module) that exports:
  - module-level constants `_LIVE_WRITE_BYPASS_ENV = "AEAT_LIVE_WRITE_UNSAFE_BYPASS"`, `_LIVE_WRITE_CONFIRM_ENV = "AEAT_LIVE_WRITE_UNSAFE_BYPASS_CONFIRM"`, `_LIVE_WRITE_CONFIRM_PHRASE = "I ACCEPT THE RISK OF FILING A LIVE TAX RETURN"`.
  - a private `_live_write_bypass_active() -> bool` helper returning `True` iff all three of: `os.environ.get(_LIVE_WRITE_BYPASS_ENV) == "1"` AND `os.environ.get(_LIVE_WRITE_CONFIRM_ENV) == _LIVE_WRITE_CONFIRM_PHRASE` AND `sys.stdin.isatty()` hold.
  - a public `apply(config, items)` callable implementing the contract:
    - For each item, compute `owned = {m.name for m in item.iter_markers()}`.
    - `access = owned & {"unit", "live_read", "live_write"}`. If `len(access) != 1`, raise `pytest.UsageError(f"{item.nodeid}: must carry exactly one of {{unit, live_read, live_write}}, found {access or 'none'}")`.
    - If no marker name starts with `domain_`, raise `pytest.UsageError(f"{item.nodeid}: must carry at least one domain_* marker")`.
    - If `"live_write" in access` and `not _live_write_bypass_active()`, DROP the item (do not append to `remaining`). Do not skip; dropped items must be invisible downstream of collection. Emit a single session-level warning via `config.issue_config_time_warning` (or a `pytest.PytestWarning` fallback) at the first drop so operators understand why `-m live_write` returned zero items.
    - At end, `items[:] = remaining`.
- Create a new repo-root `conftest.py` at `Y:/code/aeat-worktrees/feature-163-pytest-markers/conftest.py` that imports `apply` from the shared helper and defines `pytest_collection_modifyitems(config, items)` as a thin wrapper calling `apply(config, items)`. The planning-time probe established that this root-level conftest is the canonical host for `src/aeat/...` items.
- Update `tests/conftest.py` to also import the shared helper and define its own `pytest_collection_modifyitems` thin wrapper. Pytest deduplicates hooks across conftest locations by calling each conftest's hook, so the shared helper must be idempotent - and `apply()` is (it enforces invariants on items it receives, and items are filtered in-place). In practice, items collected under `src/aeat/` are processed by the root-level wrapper and items collected under `tests/` are processed by both; the second pass is a no-op because the item-level marker sets are identical. This double-invocation tolerance is by design.
- Google-scratch live_read tests must not be filtered out; they are `live_read`, not `live_write`.
- The hook MUST NOT consult `AEAT_LIVE_SUBMIT_ENABLED`; that env gate belongs to charter `R3` and is not part of this layer.
- Add a Google-style module docstring to `tests/_marker_hook.py` describing the three-factor bypass, drop-vs-skip rationale, and the double-invocation tolerance. Keep the existing docstring in `tests/conftest.py` and extend it with one sentence pointing at the shared helper.

Files touched:

- `Y:/code/aeat-worktrees/feature-163-pytest-markers/tests/_marker_hook.py` (new)
- `Y:/code/aeat-worktrees/feature-163-pytest-markers/conftest.py` (new; repo-root)
- `Y:/code/aeat-worktrees/feature-163-pytest-markers/tests/conftest.py`

Dependencies: step 1.1 (markers registered) must land in the same commit or earlier to avoid `PytestUnknownMarkWarning` during the hook run.

Verification commands:

- `uv run pytest --collect-only -m live_write -q` must print "0 tests collected" with no `AEAT_LIVE_WRITE_UNSAFE_BYPASS` env vars set.
- `uv run pytest --collect-only -m live_read -q` must collect a positive count (14 modules per the research inventory).
- `uv run pytest --collect-only -q 2>&1 | head -5` must not raise a `UsageError` with all markers correctly applied after phase 3.
- `uv run pytest --collect-only src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/test_smoke.py -q` must succeed (confirms the root-level hook participates cleanly in collection under `src/aeat/`).

Rollback: `git checkout -- tests/conftest.py` reverts `tests/conftest.py`; `rm tests/_marker_hook.py conftest.py` removes the new infrastructure.

---

### Step 2.3: add tests/test_marker_integrity.py AST walker

- Name: add tests/test_marker_integrity.py AST walker
- Step summary: `.vault/exec/2026-04-17-pytest-markers/2026-04-17-pytest-markers-phase-2-step-3.md`
- Executing agent: `vaultspec-high-executor`
- References: `[[2026-04-17-pytest-markers-adr]]` section `Marker integrity test`; `[[2026-04-17-pytest-markers-research]]` sections 2.3 (inventory) and 3.3 (module-level mandate)

Description:

- Create a new `tests/test_marker_integrity.py` module. Its own module-level marker assignment MUST be `pytestmark = [pytest.mark.unit, pytest.mark.domain_infra]`; it is itself a meta-test of the suite boundary and lives under `tests/`.
- Note: this file is self-validating - the AST walker (described below) includes `tests/**/test_*.py`, so the integrity test re-examines itself on each run and will fail if its own marker pair drifts. No separate phase-3 inventory entry is needed for it.
- The module discovers every file under `src/aeat/` and `tests/` matching `test_*.py` or `_test_*.py`, excluding any `__init__.py`, and walks each file via `ast.parse` (including itself).
- For each discovered file the walker must:
  - Find the first top-level `ast.Assign` node whose single target is a `Name` bound to `pytestmark`. If none exists, fail with a message naming the file.
  - Assert the assigned value is an `ast.List` or `ast.Tuple`.
  - For each element, require an `ast.Attribute` chain of the shape `pytest.mark.<name>` and record `<name>`. Any other shape (call expression, subscript, conditional) is rejected.
  - Classify recorded names into `access = names & {"unit", "live_read", "live_write"}` and `domains = {n for n in names if n.startswith("domain_")}`.
  - Assert `len(access) == 1` with a message that includes the file path and the names set.
  - Assert `len(domains) >= 1` with the same error shape.
- The test walks `pathlib.Path(__file__).resolve().parents[1]` to find the repo root, then globs `src/aeat/**/test_*.py`, `src/aeat/**/_test_*.py`, `tests/**/test_*.py`, and `tests/**/_test_*.py`. It MUST skip any `tests/fixtures/**` helper `.py` files that are not test modules. It does NOT skip itself - self-validation is intentional (see the self-validation note above).
- The test is parametrized over discovered files so each failing module surfaces as its own failure line rather than one aggregated assertion.
- Do NOT attempt to import the test modules; AST-only walk is sufficient and avoids collection-order coupling.

Files touched:

- `Y:/code/aeat-worktrees/feature-163-pytest-markers/tests/test_marker_integrity.py` (new)

Dependencies: step 2.2 (hook) is independent; this step can be authored before the migration phase runs but will fail until phase 3 completes, which is the intended acceptance gate.

Verification commands:

- `uv run pytest tests/test_marker_integrity.py -v` must pass after phase 3 completes (and will fail during the migration, which is by design).

Rollback: delete the file.

---

### Step 2.4: confirm hook reach from src/aeat/ collection root (confirmatory)

- Name: confirm hook reach from src/aeat/ collection root (confirmatory)
- Step summary: `.vault/exec/2026-04-17-pytest-markers/2026-04-17-pytest-markers-phase-2-step-4.md`
- Executing agent: `vaultspec-code-reviewer`
- References: `[[2026-04-17-pytest-markers-research]]` section 8 gotcha 6; `[[2026-04-17-pytest-markers-adr]]` alternatives considered (root conftest vs. tests conftest); planning-time probe recorded in this plan

Description:

- This step is confirmatory only: the planning-time probe (see `Planning-time probe: hook reach` section above) has already established that a `tests/conftest.py`-only hook does NOT reach `src/aeat/...` items, and that the repo-root `conftest.py` does. Step 2.2 has therefore already installed the hook at the correct location (repo-root `conftest.py`, with a shared `tests/_marker_hook.py` helper and a parallel wrapper in `tests/conftest.py`). No branching decision remains.
- Execute the deterministic confirmation:
  1. Temporarily edit a single file under `src/aeat/adapters/outbound/aeat/export/` (for example `src/aeat/adapters/outbound/aeat/export/test_engine.py`) to add `pytest.mark.live_write` to its `pytestmark` list in place of the existing access marker.
  2. Run `uv run pytest --collect-only src/aeat/adapters/outbound/aeat/export/test_engine.py -q` with no bypass env vars set.
  3. Expect: the item is dropped (zero collected). A session-level warning may surface.
  4. Revert the temporary edit with `git checkout -- src/aeat/adapters/outbound/aeat/export/test_engine.py` before closing the step.
- The decision tree that was originally specified in this step (leave in `tests/conftest.py` vs. promote to a shared helper) is retired because the planning-time probe has already chosen the promotion path.

Files touched: none (the ad-hoc edit is reverted before the step closes).

Dependencies: step 2.2 and phase 3 landed (so the file under edit already carries a legal `pytestmark`).

Verification commands:

- `uv run pytest --collect-only src/aeat/adapters/outbound/aeat/export/test_engine.py -q` with the ad-hoc `live_write` tag returns zero collected.
- `uv run pytest --collect-only src/aeat/adapters/outbound/aeat/export/test_engine.py -q` after revert returns the pre-refactor item count.

Rollback: `git checkout -- src/aeat/adapters/outbound/aeat/export/test_engine.py` (or the file the reviewer picked).

---

## Phase 3: migrate every test module to module-level pytestmark

This phase enumerates every test module in the repository, maps each to its final module-level `pytestmark` expression, and strips per-function `@pytest.mark.unit` / `@pytest.mark.live` decorators. The inventory below is copied from the research document and extended with the explicit `pytestmark` expression each file receives.

Convention: every file receives `import pytest` (if not already present) and a single top-level assignment of the shape `pytestmark = [pytest.mark.<access>, pytest.mark.<domain>]`, placed immediately after the module docstring and top-level imports. Per-function markers of the access or domain shape are removed. Non-access, non-domain markers (notably `@pytest.mark.skipif`, `@pytest.mark.parametrize`) are preserved unchanged.

Mixed-access module check: research found zero modules that mix `unit` and `live_read` test functions. Phase 2 step 2.3 (integrity test) is the backstop that surfaces any overlooked case. If the integrity test fails with a mixed-access module, the executor MUST split the module into two before continuing rather than use per-function overrides.

### Step 3.1: migrate domain_aeat_remote test modules

- Name: migrate domain_aeat_remote test modules
- Step summary: `.vault/exec/2026-04-17-pytest-markers/2026-04-17-pytest-markers-phase-3-step-1.md`
- Executing agent: `vaultspec-standard-executor`
- References: `[[2026-04-17-pytest-markers-research]]` section 2.3.1

Description: apply module-level `pytestmark` and strip per-function access markers in the following files.

Inventory (path -> new `pytestmark`):

- `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/test_certificate.py` -> `[pytest.mark.unit, pytest.mark.domain_aeat_remote]`
- `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/test_certificate_live.py` -> `[pytest.mark.live_read, pytest.mark.domain_aeat_remote]`
- `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/test_health.py` -> `[pytest.mark.unit, pytest.mark.domain_aeat_remote]`
- `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/test_smoke.py` -> `[pytest.mark.unit, pytest.mark.domain_aeat_remote]`
- `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/test_evasion.py` -> `[pytest.mark.unit, pytest.mark.domain_aeat_remote]`
- `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/test_live_evasion.py` -> `[pytest.mark.live_read, pytest.mark.domain_aeat_remote]`
- `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/test_profile.py` -> `[pytest.mark.unit, pytest.mark.domain_aeat_remote]`
- `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/test_session.py` -> `[pytest.mark.unit, pytest.mark.domain_aeat_remote]`
- `src/aeat/inbox/test_classifier.py` -> `[pytest.mark.unit, pytest.mark.domain_aeat_remote]`
- `src/aeat/inbox/test_deadline.py` -> `[pytest.mark.unit, pytest.mark.domain_aeat_remote]`
- `src/aeat/inbox/test_fetcher.py` -> `[pytest.mark.unit, pytest.mark.domain_aeat_remote]`
- `src/aeat/inbox/test_live_inbox.py` -> `[pytest.mark.live_read, pytest.mark.domain_aeat_remote]`
- `src/aeat/inbox/test_models.py` -> `[pytest.mark.unit, pytest.mark.domain_aeat_remote]`
- `src/aeat/domain/justificante/test_parser.py` -> `[pytest.mark.unit, pytest.mark.domain_aeat_remote]`
- `src/aeat/domain/justificante/test_verify_live.py` -> `[pytest.mark.live_read, pytest.mark.domain_aeat_remote]`
- `src/aeat/status/test_cache.py` -> `[pytest.mark.unit, pytest.mark.domain_aeat_remote]`
- `src/aeat/status/test_cache_key.py` -> `[pytest.mark.unit, pytest.mark.domain_aeat_remote]`
- `src/aeat/status/test_errors.py` -> `[pytest.mark.unit, pytest.mark.domain_aeat_remote]`
- `src/aeat/status/test_live.py` -> `[pytest.mark.live_read, pytest.mark.domain_aeat_remote]`
- `src/aeat/status/test_models.py` -> `[pytest.mark.unit, pytest.mark.domain_aeat_remote]`
- `src/aeat/status/test_reader.py` -> `[pytest.mark.unit, pytest.mark.domain_aeat_remote]`
- `src/aeat/status/test_site_health.py` -> `[pytest.mark.unit, pytest.mark.domain_aeat_remote]`
- `src/aeat/status/_parsers/test_expedientes.py` -> `[pytest.mark.unit, pytest.mark.domain_aeat_remote]`
- `src/aeat/domain/casillas/test_live_cli.py` -> `[pytest.mark.live_read, pytest.mark.domain_aeat_remote]`
- `src/aeat/domain/casillas/test_smoke.py` -> `[pytest.mark.unit, pytest.mark.domain_aeat_remote]`
- `src/aeat/domain/casillas/_test_catalogue.py` -> `[pytest.mark.unit, pytest.mark.domain_aeat_remote]`
- `src/aeat/domain/casillas/_test_cli.py` -> `[pytest.mark.unit, pytest.mark.domain_aeat_remote]`
- `src/aeat/application/sync/test_bounded_policy.py` -> `[pytest.mark.unit, pytest.mark.domain_aeat_remote]`
- `src/aeat/application/sync/test_classifier.py` -> `[pytest.mark.unit, pytest.mark.domain_aeat_remote]`
- `src/aeat/application/sync/test_live_sync.py` -> `[pytest.mark.live_read, pytest.mark.domain_aeat_remote]`
- `src/aeat/application/sync/test_repository.py` -> `[pytest.mark.unit, pytest.mark.domain_aeat_remote]`
- `src/aeat/application/sync/test_runner.py` -> `[pytest.mark.unit, pytest.mark.domain_aeat_remote]`
- `src/aeat/application/sync/test_smoke.py` -> `[pytest.mark.unit, pytest.mark.domain_aeat_remote]`
- `src/aeat/application/sync/test_strategies.py` -> `[pytest.mark.unit, pytest.mark.domain_aeat_remote]`
- `src/aeat/application/sync/test_wire.py` -> `[pytest.mark.unit, pytest.mark.domain_aeat_remote]`
- `src/aeat/domain/portals/test_smoke.py` -> `[pytest.mark.unit, pytest.mark.domain_aeat_remote]`

Files touched: the 36 paths above (each as an absolute path under `Y:/code/aeat-worktrees/feature-163-pytest-markers/`).

Dependencies: none within phase 3; can run in parallel with other phase 3 steps.

Verification commands:

- `uv run pytest src/aeat/auth src/aeat/browser src/aeat/inbox src/aeat/justificante src/aeat/status src/aeat/casillas src/aeat/sync src/aeat/portals -m unit -q` must pass.
- `uv run pytest tests/test_marker_integrity.py -k domain_aeat_remote -v` (if the integrity test is already in place) must report no failures in these files.

Rollback: `git checkout -- <file>` per file reverts cleanly; test function bodies are not modified.

---

### Step 3.2: migrate domain_submission test modules

- Name: migrate domain_submission test modules
- Step summary: `.vault/exec/2026-04-17-pytest-markers/2026-04-17-pytest-markers-phase-3-step-2.md`
- Executing agent: `vaultspec-high-executor`
- References: `[[2026-04-17-pytest-markers-research]]` section 2.3.2; `[[2026-04-17-pytest-markers-adr]]` rationale for `domain_submission` carve-out; charter `#116` R5

Description: apply module-level `pytestmark` to the write-capable boundary. Every currently `live`-marked file in this domain is a dry-run-only probe and migrates to `live_read`; zero files become `live_write`. Per charter R5 the `SubmissionEngine.__init__` runtime refusal remains untouched.

Inventory:

- `src/aeat/application/filing/test_complementaria.py` -> `[pytest.mark.unit, pytest.mark.domain_submission]`
- `src/aeat/application/filing/test_filing.py` -> `[pytest.mark.unit, pytest.mark.domain_submission]`
- `src/aeat/application/filing/test_live_complementaria.py` -> `[pytest.mark.live_read, pytest.mark.domain_submission]`
- `src/aeat/application/filing/test_modelo_303_390.py` -> `[pytest.mark.unit, pytest.mark.domain_submission]`
- `src/aeat/adapters/outbound/aeat/export/test_engine.py` -> `[pytest.mark.unit, pytest.mark.domain_submission]`
- `src/aeat/adapters/outbound/aeat/export/test_errors.py` -> `[pytest.mark.unit, pytest.mark.domain_submission]`
- `src/aeat/adapters/outbound/aeat/export/test_live_submission.py` -> `[pytest.mark.live_read, pytest.mark.domain_submission]`
- `src/aeat/adapters/outbound/aeat/export/test_models.py` -> `[pytest.mark.unit, pytest.mark.domain_submission]`
- `src/aeat/adapters/outbound/aeat/export/test_preflight.py` -> `[pytest.mark.unit, pytest.mark.domain_submission]`
- `src/aeat/adapters/outbound/aeat/export/test_safety_helpers.py` -> `[pytest.mark.unit, pytest.mark.domain_submission]`
- `src/aeat/adapters/outbound/aeat/export/_submitters/test_modelo130.py` -> `[pytest.mark.unit, pytest.mark.domain_submission]`

Files touched: the 11 paths above.

Dependencies: none within phase 3.

Verification commands:

- `uv run pytest src/aeat/filing src/aeat/submission -m unit -q` must pass.
- `uv run pytest --collect-only src/aeat/adapters/outbound/aeat/export/test_live_submission.py -m live_read` must collect the file's items; `... -m live_write` must collect zero.

Rollback: per-file `git checkout --`.

---

### Step 3.3: migrate domain_financial_input test modules

- Name: migrate domain_financial_input test modules
- Step summary: `.vault/exec/2026-04-17-pytest-markers/2026-04-17-pytest-markers-phase-3-step-3.md`
- Executing agent: `vaultspec-standard-executor`
- References: `[[2026-04-17-pytest-markers-research]]` section 2.3.3

Description: apply module-level `pytestmark = [pytest.mark.unit, pytest.mark.domain_financial_input]` to every file in the inventory. No `live_*` tests in this domain.

Inventory:

- `src/aeat/domain/financial/categories/test_profile.py`
- `src/aeat/domain/financial/categories/test_proportionality.py`
- `src/aeat/domain/financial/categories/test_registry.py`
- `src/aeat/domain/financial/categories/test_spending_category.py`
- `src/aeat/domain/financial/invoices/test_catalogue.py`
- `src/aeat/domain/financial/invoices/test_cli.py`
- `src/aeat/domain/financial/invoices/test_models.py`
- `src/aeat/domain/financial/invoices/test_reconciliation.py`
- `src/aeat/domain/financial/invoices/test_validators.py`
- `src/aeat/domain/financial/providers/test_base.py`
- `src/aeat/domain/financial/providers/test_csv.py`
- `src/aeat/domain/financial/providers/test_ofx.py`
- `src/aeat/domain/financial/providers/test_xlsx.py`
- `src/aeat/domain/financial/transactions/test_catalogue.py`
- `src/aeat/domain/financial/transactions/test_cli.py`
- `src/aeat/domain/financial/transactions/test_models.py`
- `src/aeat/domain/financial/vat/test_categories.py`
- `src/aeat/domain/financial/vat/test_corpus.py`
- `src/aeat/domain/financial/vat/test_rates.py`
- `src/aeat/domain/financial/vat/test_rules.py`
- `src/aeat/domain/financial/vat/test_verify.py`
- `src/aeat/entrypoints/cli/financial/test_cli.py`

Files touched: the 22 paths above.

Dependencies: none.

Verification: `uv run pytest src/aeat/financial src/aeat/entrypoints/cli/financial -m unit -q` passes.

Rollback: per-file `git checkout --`.

---

### Step 3.4: migrate domain_local_state test modules

- Name: migrate domain_local_state test modules
- Step summary: `.vault/exec/2026-04-17-pytest-markers/2026-04-17-pytest-markers-phase-3-step-4.md`
- Executing agent: `vaultspec-standard-executor`
- References: `[[2026-04-17-pytest-markers-research]]` section 2.3.4

Description: apply module-level `pytestmark = [pytest.mark.unit, pytest.mark.domain_local_state]`. No `live_*` tests in this domain.

Inventory:

- `src/aeat/adapters/persistence/storage/test_smoke.py`
- `src/aeat/adapters/persistence/storage/_test_constraints.py`
- `src/aeat/adapters/persistence/storage/_test_engine.py`
- `src/aeat/adapters/persistence/storage/_test_migrations.py`
- `src/aeat/adapters/persistence/storage/_test_records.py`
- `src/aeat/adapters/persistence/storage/_test_repository.py`
- `src/aeat/adapters/persistence/storage/_test_session.py`
- `src/aeat/domain/modelos/test_applicability.py`
- `src/aeat/domain/modelos/test_casilla_cross_reference.py`
- `src/aeat/domain/modelos/test_citations.py`
- `src/aeat/domain/modelos/test_cli.py`
- `src/aeat/domain/modelos/test_codes.py`
- `src/aeat/domain/modelos/test_metadata.py`
- `src/aeat/domain/modelos/test_registry.py`
- `src/aeat/domain/modelos/test_smoke.py`
- `src/aeat/domain/normatives/test_loader.py`
- `src/aeat/domain/normatives/test_lookup_and_cite.py`
- `src/aeat/domain/normatives/test_schema.py`
- `src/aeat/domain/normatives/test_verify.py`
- `src/aeat/domain/manuals/test_fetch.py`
- `src/aeat/domain/manuals/test_loader.py`
- `src/aeat/domain/manuals/test_schema.py`
- `src/aeat/domain/manuals/test_verify.py`
- `src/aeat/corpus/test_smoke.py`
- `src/aeat/domain/schema/test_smoke.py`
- `src/aeat/domain/deadlines/test_applies.py`
- `src/aeat/domain/deadlines/test_calendar.py`
- `src/aeat/domain/deadlines/test_engine.py`
- `src/aeat/domain/deadlines/test_models.py`
- `src/aeat/entrypoints/cli/deadlines/test_cli.py`

Files touched: the 30 paths above.

Dependencies: none.

Verification: `uv run pytest src/aeat/storage src/aeat/models src/aeat/normatives src/aeat/manuals src/aeat/corpus src/aeat/schema src/aeat/deadlines src/aeat/entrypoints/cli/deadlines -m unit -q` passes.

Rollback: per-file `git checkout --`.

---

### Step 3.5: migrate domain_mediation test modules

- Name: migrate domain_mediation test modules
- Step summary: `.vault/exec/2026-04-17-pytest-markers/2026-04-17-pytest-markers-phase-3-step-5.md`
- Executing agent: `vaultspec-standard-executor`
- References: `[[2026-04-17-pytest-markers-research]]` section 2.3.5

Description: apply module-level `pytestmark` per inventory.

Inventory:

- `src/aeat/application/workflow/test_engine.py` -> `[pytest.mark.unit, pytest.mark.domain_mediation]`
- `src/aeat/application/workflow/test_live.py` -> `[pytest.mark.live_read, pytest.mark.domain_mediation]`
- `src/aeat/application/workflow/test_models.py` -> `[pytest.mark.unit, pytest.mark.domain_mediation]`
- `src/aeat/application/workflow/test_persistence.py` -> `[pytest.mark.unit, pytest.mark.domain_mediation]`
- `src/aeat/adapters/outbound/llm/test_live_anthropic.py` -> `[pytest.mark.live_read, pytest.mark.domain_mediation]`
- `src/aeat/adapters/outbound/llm/test_smoke.py` -> `[pytest.mark.unit, pytest.mark.domain_mediation]`
- `src/aeat/adapters/outbound/llm/_test_cache.py` -> `[pytest.mark.unit, pytest.mark.domain_mediation]`
- `src/aeat/adapters/outbound/llm/_test_client.py` -> `[pytest.mark.unit, pytest.mark.domain_mediation]`
- `src/aeat/adapters/outbound/llm/_test_models.py` -> `[pytest.mark.unit, pytest.mark.domain_mediation]`
- `src/aeat/adapters/outbound/llm/_test_prompts.py` -> `[pytest.mark.unit, pytest.mark.domain_mediation]`
- `src/aeat/adapters/outbound/llm/_test_translation.py` -> `[pytest.mark.unit, pytest.mark.domain_mediation]`
- `src/aeat/adapters/outbound/llm/_test_usage.py` -> `[pytest.mark.unit, pytest.mark.domain_mediation]`
- `src/aeat/core/i18n/test_i18n.py` -> `[pytest.mark.unit, pytest.mark.domain_mediation]`
- `src/aeat/domain/testing/test_testing.py` -> `[pytest.mark.unit, pytest.mark.domain_mediation]`

Files touched: the 14 paths above.

Dependencies: none.

Verification: `uv run pytest src/aeat/workflow src/aeat/llm src/aeat/i18n src/aeat/testing -m unit -q` passes.

Rollback: per-file `git checkout --`.

---

### Step 3.6: migrate domain_infra test modules

- Name: migrate domain_infra test modules
- Step summary: `.vault/exec/2026-04-17-pytest-markers/2026-04-17-pytest-markers-phase-3-step-6.md`
- Executing agent: `vaultspec-standard-executor`
- References: `[[2026-04-17-pytest-markers-research]]` section 2.3.6

Description: apply module-level `pytestmark` per inventory. `tests/live/test_google_fixtures_smoke.py` already lists module-level `[live, skipif]`; replace with the new list while preserving the `skipif` guard.

Inventory:

- `src/aeat/_test_auth.py` -> `[pytest.mark.unit, pytest.mark.domain_infra]`
- `src/aeat/_test_env_io.py` -> `[pytest.mark.unit, pytest.mark.domain_infra]`
- `src/aeat/entrypoints/cli/test_categories_cli.py` -> `[pytest.mark.unit, pytest.mark.domain_infra]`
- `src/aeat/entrypoints/cli/test_manual_cli.py` -> `[pytest.mark.unit, pytest.mark.domain_infra]`
- `src/aeat/entrypoints/cli/test_smoke.py` -> `[pytest.mark.unit, pytest.mark.domain_infra]`
- `src/aeat/entrypoints/cli/test_vat_cli.py` -> `[pytest.mark.unit, pytest.mark.domain_infra]`
- `src/aeat/entrypoints/cli/browser/test_health.py` -> `[pytest.mark.unit, pytest.mark.domain_infra]`
- `src/aeat/entrypoints/cli/filing/test_filing_cli.py` -> `[pytest.mark.unit, pytest.mark.domain_infra]`
- `src/aeat/entrypoints/cli/inbox/test_cli.py` -> `[pytest.mark.unit, pytest.mark.domain_infra]`
- `src/aeat/entrypoints/cli/llm/test_smoke.py` -> `[pytest.mark.unit, pytest.mark.domain_infra]`
- `src/aeat/entrypoints/cli/submission/test_cli.py` -> `[pytest.mark.unit, pytest.mark.domain_infra]`
- `src/aeat/entrypoints/cli/sync/test_cli.py` -> `[pytest.mark.unit, pytest.mark.domain_infra]`
- `src/aeat/entrypoints/cli/workflow/test_cli.py` -> `[pytest.mark.unit, pytest.mark.domain_infra]`
- `src/aeat/entrypoints/cli/_test_bootstrap.py` -> `[pytest.mark.unit, pytest.mark.domain_infra]`
- `src/aeat/entrypoints/cli/_test_cloud.py` -> `[pytest.mark.unit, pytest.mark.domain_infra]`
- `src/aeat/entrypoints/cli/_test_cloud_live.py` -> `[pytest.mark.live_read, pytest.mark.domain_infra]`
- `src/aeat/entrypoints/cli/_test_docs_helpers.py` -> `[pytest.mark.unit, pytest.mark.domain_infra]`
- `src/aeat/entrypoints/cli/_test_docs_live.py` -> `[pytest.mark.live_read, pytest.mark.domain_infra]`
- `src/aeat/entrypoints/cli/_test_doctor.py` -> `[pytest.mark.unit, pytest.mark.domain_infra]`
- `src/aeat/entrypoints/cli/_test_drive_helpers.py` -> `[pytest.mark.unit, pytest.mark.domain_infra]`
- `src/aeat/entrypoints/cli/_test_drive_live.py` -> `[pytest.mark.live_read, pytest.mark.domain_infra]`
- `src/aeat/entrypoints/cli/_test_oauth.py` -> `[pytest.mark.unit, pytest.mark.domain_infra]`
- `src/aeat/entrypoints/cli/_test_sheets_helpers.py` -> `[pytest.mark.unit, pytest.mark.domain_infra]`
- `src/aeat/entrypoints/cli/_test_sheets_live.py` -> `[pytest.mark.live_read, pytest.mark.domain_infra]`
- `src/aeat/application/setup/test_cli.py` -> `[pytest.mark.unit, pytest.mark.domain_infra]`
- `src/aeat/application/setup/test_env_writer.py` -> `[pytest.mark.unit, pytest.mark.domain_infra]`
- `src/aeat/application/setup/test_models.py` -> `[pytest.mark.unit, pytest.mark.domain_infra]`
- `src/aeat/application/setup/test_verifier.py` -> `[pytest.mark.unit, pytest.mark.domain_infra]`
- `src/aeat/application/setup/test_wizard.py` -> `[pytest.mark.unit, pytest.mark.domain_infra]`
- `tests/test_config.py` -> `[pytest.mark.unit, pytest.mark.domain_infra]`
- `tests/test_docs.py` -> `[pytest.mark.unit, pytest.mark.domain_infra]`
- `tests/test_release_config.py` -> `[pytest.mark.unit, pytest.mark.domain_infra]`
- `tests/live/test_google_fixtures_smoke.py` -> `[pytest.mark.live_read, pytest.mark.domain_infra]` (preserve existing `skipif`)

Files touched: the 33 paths above.

Dependencies: none.

Verification: `uv run pytest src/aeat/_test_auth.py src/aeat/_test_env_io.py src/aeat/cli src/aeat/setup tests/test_config.py tests/test_docs.py tests/test_release_config.py -m unit -q` passes.

Rollback: per-file `git checkout --`.

---

## Phase 4: justfile recipes

### Step 4.1: rewrite test, test-live; add test-live-read, test-domain, test-live-write

- Name: rewrite test, test-live; add test-live-read, test-domain, test-live-write
- Step summary: `.vault/exec/2026-04-17-pytest-markers/2026-04-17-pytest-markers-phase-4-step-1.md`
- Executing agent: `vaultspec-standard-executor`
- References: `[[2026-04-17-pytest-markers-adr]]` section `just recipes`; `[[2026-04-17-pytest-markers-research]]` section 6

Description: rewrite the four recipes below and add `test-live-write` as a documentation surface. The `just` file uses `set windows-shell := ["pwsh.exe", ...]` so recipes must continue to be compatible with both posix and pwsh invocations; the pytest invocations below are shell-agnostic.

- `test` -> `uv run pytest` (unit-only via `addopts = "-m 'unit'"`). Unchanged body, updated comment: "Run the pytest suite (unit-only by default via pyproject addopts)."
- `test-live` -> `uv run pytest -m "unit or live_read"`. Comment: "Run unit plus live_read tests (requires AEAT_LIVE_TESTS_ENABLED=1 for live_read items)."
- `test-live-read` (new) -> `uv run pytest -m "live_read"`. Comment: "Run only live_read tests."
- `test-domain DOMAIN` (new) -> `uv run pytest -m "unit and domain_{{DOMAIN}}"`. Comment: "Run unit tests in a single domain, e.g. `just test-domain financial_input`."
- `test-live-write` (new, documentation surface) -> echo a multi-line warning describing the three-factor bypass requirement (env var set to `1`, confirm env var equal to the phrase byte-for-byte, interactive TTY) and then invoke `uv run pytest -m live_write`. The recipe is expected to return zero collected items under normal operation; the recipe exists so the bypass incantation is documented in the operator-facing surface. The warning text MUST cite charter `#116` R1 verbatim and state explicitly that the recipe does NOT enable a live submission.

Files touched:

- `Y:/code/aeat-worktrees/feature-163-pytest-markers/justfile`

Dependencies: phase 1 and phase 3 complete (otherwise `-m 'unit'` catches zero items in un-migrated files).

Verification commands:

- `just test` exits 0 with the migrated suite.
- `just test-live-read` collects 14 items and respects `AEAT_LIVE_TESTS_ENABLED` gating.
- `just test-live-write` prints the bypass warning and collects zero items under default env.

Rollback: `git checkout -- justfile`.

---

## Phase 5: docs + env.example

### Step 5.1: update CLAUDE.md testing paragraph

- Name: update CLAUDE.md testing paragraph
- Step summary: `.vault/exec/2026-04-17-pytest-markers/2026-04-17-pytest-markers-phase-5-step-1.md`
- Executing agent: `vaultspec-standard-executor`
- References: `[[2026-04-17-pytest-markers-adr]]` section `Implementation` (documentation churn bullet)

Description: rewrite line 4 (the `Testing uses pytest. ...` paragraph) of `CLAUDE.md` to describe the new marker taxonomy. The replacement paragraph MUST mention:

- Axis A: every test carries exactly one of `unit`, `live_read`, `live_write`.
- Axis B: every test carries at least one `domain_*` marker (six options: `domain_aeat_remote`, `domain_submission`, `domain_financial_input`, `domain_local_state`, `domain_mediation`, `domain_infra`).
- Mandate: markers are applied at module level via `pytestmark = [...]`; per-function access/domain markers are forbidden.
- Opt-in: `live_read` requires `AEAT_LIVE_TESTS_ENABLED=1`; Google Workspace `live_read` additionally requires `AEAT_LIVE_TESTS_GOOGLE=1`.
- Ban: `live_write` tests are collection-banned by default; no `live_write` tests exist today; see `tests/README.md` and charter `#116`.
- Mocks/stubs: unit tests may use mocks; live tests (both `live_read` and `live_write`) must never contain mocks, patches, shadows, fakes, or stubs.

Files touched:

- `Y:/code/aeat-worktrees/feature-163-pytest-markers/CLAUDE.md`

Dependencies: none.

Verification commands:

- `grep -n "live_read\|live_write\|domain_" CLAUDE.md` shows the new taxonomy is documented.
- `uv run pytest tests/test_docs.py -m unit -q` (if `test_docs.py` cross-checks CLAUDE.md) passes.

Rollback: `git checkout -- CLAUDE.md`.

---

### Step 5.2: create tests/README.md

- Name: create tests/README.md
- Step summary: `.vault/exec/2026-04-17-pytest-markers/2026-04-17-pytest-markers-phase-5-step-2.md`
- Executing agent: `vaultspec-standard-executor`
- References: `[[2026-04-17-pytest-markers-adr]]` section `Implementation`; charter `#116`

Description: author a new `tests/README.md` that serves as the canonical operator reference for the marker taxonomy and the three-factor bypass. Sections:

- Overview paragraph referencing charter `#116` and the ADR by filename.
- Marker table: nine rows (`unit`, `live_read`, `live_write`, six `domain_*`). Each row: marker name, one-line semantics, selection command example.
- Module-level mandate: explain `pytestmark = [...]` shape, show a canonical header, and note that per-function access or domain markers are forbidden.
- Live_write ban: explain drop-not-skip, the three factors, and state verbatim the confirmation phrase: `I ACCEPT THE RISK OF FILING A LIVE TAX RETURN`. Warn that setting the bypass does NOT enable a live submission (charter `R3` / `R5` still apply).
- Bypass incantation: show the exact shell one-liner that sets both env vars and runs `uv run pytest -m live_write` from an interactive terminal. Immediately follow with a "DO NOT RUN unless you are about to file a legally binding tax return" banner.
- Cross-reference to `scripts/README.md` for Google fixture provisioning and `CLAUDE.md` for the trilingual testing contract.

Files touched:

- `Y:/code/aeat-worktrees/feature-163-pytest-markers/tests/README.md` (new)

Dependencies: none.

Verification commands:

- `grep -c "I ACCEPT THE RISK OF FILING A LIVE TAX RETURN" tests/README.md` must return `>= 1`.
- `grep -n "live_write" tests/README.md` shows the ban section present.

Rollback: delete the file.

---

## Phase 6: verification

### Step 6.1: run the full verification matrix

- Name: run the full verification matrix
- Step summary: `.vault/exec/2026-04-17-pytest-markers/2026-04-17-pytest-markers-phase-6-step-1.md`
- Executing agent: `vaultspec-code-reviewer`
- References: `[[2026-04-17-pytest-markers-adr]]` section `Verification after the refactor`; `[[2026-04-17-pytest-markers-research]]` section 8 (gotchas)

Description: run every verification command below and record the exit status and summary into the step record. Any failure aborts the phase and sends control back to the relevant earlier step.

Verification commands (core suite):

- `uv run pytest -m unit` -> expected green across the whole tree.
- `uv run pytest -m "unit or live_read"` -> expected green with `AEAT_LIVE_TESTS_ENABLED=1` (live_read items run), expected green with it unset (live_read items skip via existing gates, unit items run).
- `uv run pytest -m live_write` -> expected zero collected; a warning banner from the collection hook is acceptable.
- `uv run pytest tests/test_marker_integrity.py` -> expected green.
- `uv run pytest --collect-only -q 2>&1 | grep -i PytestUnknownMarkWarning` -> expected empty.
- `uv run pytest tests/test_config.py` -> expected green (env-alignment invariant).
- `uv run pytest tests/test_release_config.py` -> expected green (GHA-disabled invariant).
- `uv run ruff check src tests` -> expected clean.
- `uv run ty check src tests` -> expected clean.
- `grep -rn "@pytest.mark.live\b" src tests` -> expected zero matches (word boundary avoids matching `live_read`/`live_write`).
- `grep -n '"live"' pyproject.toml` -> expected zero matches (stale marker removed).

Three-factor bypass invariants (factor-by-factor). The `uv run pytest` command as invoked by CI and by developer terminals is NOT a TTY in the default case; this means the TTY factor already fails for the sub-checks below, and partial env-set probes on their own do not prove the env-var gates work. The sub-checks are therefore framed as "which factor is missing" to make the invariant explicit rather than implicit.

- `6.1a (automated): no env vars, non-TTY` -> `uv run pytest --collect-only src/aeat/adapters/outbound/aeat/export/ -m live_write -q` expected zero collected. Covers the 3-factor default; no factor is present.
- `6.1b (automated): both env vars set, non-TTY` -> `AEAT_LIVE_WRITE_UNSAFE_BYPASS=1 AEAT_LIVE_WRITE_UNSAFE_BYPASS_CONFIRM="I ACCEPT THE RISK OF FILING A LIVE TAX RETURN" uv run pytest --collect-only src/aeat/adapters/outbound/aeat/export/ -m live_write -q` expected zero collected. Isolates the TTY factor: both env vars are present, only the TTY factor is missing, so collection must still drop.
- `6.1c (manual-only, not automated): both env vars set + interactive TTY` -> a human operator in an interactive terminal runs the same command with both env vars set and verifies that a temporary `live_write`-tagged test (created and reverted in-step like phase 2 step 2.4) IS collected. This sub-check is documented in `tests/README.md` and executed once per implementation cycle by the reviewer; automated TTY simulation is out of scope of this plan.
- `6.1d (automated): confirm env set alone, non-TTY` -> expected zero collected. Isolates the bypass env var: the confirmation phrase on its own does nothing.
- `6.1e (automated): bypass env set alone, non-TTY` -> expected zero collected. Isolates the confirmation phrase: the bypass env var on its own does nothing.

Files touched: none (read-only verification; the step record captures results).

Dependencies: every preceding step complete.

Rollback: not applicable; failures trigger targeted re-execution of the earlier step that owns the defect.

---

## Parallelization

- Phase 1 (marker registration), phase 2 steps 2.1/2.2/2.3, and phase 3 steps 3.1-3.6 can be authored in parallel: the pyproject change, the hook, the integrity test, and the per-domain file migrations do not share mutable state.
- Phase 2 step 2.4 (hook reach confirmation) must run after step 2.2 AND at least one phase 3 migration step has landed (because the confirmation edits an existing `pytestmark` list in a phase-3-migrated file).
- Phase 3 steps are independent per-domain and can execute in six parallel sub-agent threads; each touches a disjoint file set.
- Phase 4 (justfile) is independent of phase 2/3 bodies but its verification depends on phase 3 being complete so `just test` finds only unit items.
- Phase 5 docs are independent; phase 5 step 5.2 can land in parallel with phase 3 migrations.
- Phase 6 verification is serial and runs last.

## Verification

Mission success criteria tied to the ADR and research inputs:

- `uv run pytest -m unit` is green; developer inner-loop behaviour matches the pre-refactor `-m 'not live'` default in scope and speed.
- `uv run pytest -m live_read` collects the 14 `live_read` modules identified in the research inventory and honours the existing `AEAT_LIVE_TESTS_ENABLED` / `AEAT_LIVE_TESTS_GOOGLE` gates without modification.
- `uv run pytest -m live_write` collects zero items under default env. The bypass is structurally three-factor and no single factor can defeat it; step 6.1 isolates each factor (no env set, each env set alone, both envs set but non-TTY) and the manual-only sub-check 6.1c validates the positive path with all three factors present.
- `tests/test_marker_integrity.py` is green and fails clearly on any future module that drifts from the mandate.
- `tests/test_config.py` is green after the two new env vars land; env-alignment invariant holds.
- `tests/test_release_config.py` is green; no `.github/workflows/*` file added.
- Zero `PytestUnknownMarkWarning` across the suite.
- `grep -rn "@pytest.mark.live\b" src tests` returns zero matches; the stale binary marker is fully retired.
- Charter `#116` R1..R6 remain verbatim; `AEAT_LIVE_SUBMIT_ENABLED` and `SubmissionEngine.__init__` are untouched. This is verified by `git diff src/aeat/adapters/outbound/aeat/export/_engine.py` (or equivalent) being empty and by `grep -n "AEAT_LIVE_SUBMIT_ENABLED" src/aeat/config.py env/.env.example` returning the same lines as before the refactor.
- A reviewer's spot-check of three randomly selected migrated files confirms test function bodies are byte-for-byte identical to pre-refactor (only marker metadata changed).

Honest coverage caveats:

- The plan ships dormant `live_write` infrastructure. The ban mechanism cannot be exercised end-to-end without a real `live_write` test to drop, so the verification relies on a temporary ad-hoc `live_write` tag during phase 2 step 2.4 that is reverted before commit. This is an accepted limitation; adding a permanent `live_write` test would violate charter `R1`.
- The three-factor bypass cannot be automatically tested in full (the TTY factor requires an interactive terminal). Phase 6 verifies that any of the three factors missing produces a zero collection; the positive-path collection (all three factors present) is documented in `tests/README.md` and validated manually once by the implementer and again by the reviewer.
- The integrity test walks AST, not live pytest collection, so a pathological file that defines `pytestmark` under a conditional or at non-module scope would escape it. The plan accepts this as the cost of a deterministic walk; the collection hook is the runtime backstop.

## Explicit Plan Review

- **Scope check:** test-infrastructure refactor only. The only production-code touch is two additive `Settings` fields in `src/aeat/config.py` (plus mirrors in `env/.env.example`), which the ADR explicitly mandates for env-alignment.
- **Charter invariants check:** `AEAT_LIVE_SUBMIT_ENABLED` env gate (`R3`) and `SubmissionEngine.__init__` runtime refusal (`R5`) are not touched. The bypass env vars are distinct and the collection hook does not consult the submit env. The plan restates this in phase 2 step 2.1 and phase 6.
- **Marker retirement check:** the stale `live` marker is removed in the same commit as the hook and phase 3 migration, so no interim state emits `PytestUnknownMarkWarning`.
- **Per-function decorator audit check:** phase 3 steps explicitly strip `@pytest.mark.unit` / `@pytest.mark.live`; the integrity test and `grep -rn "@pytest.mark.live\b"` backstop enforce the completeness.
- **Test body preservation check:** phase 6 verification includes a spot-check of three files for byte-identical function bodies.
- **Approval check:** plan is persisted; awaiting user approval before execution (per vaultspec default).
