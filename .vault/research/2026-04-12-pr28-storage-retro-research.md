---
tags:
  - '#research'
  - '#pr28-storage-retro'
date: '2026-04-12'
modified: '2026-04-12'
related:
  - '[[2026-04-12-data-storage-research]]'
  - '[[2026-04-12-pr28-storage-retro-audit]]'
---

# `pr28-storage-retro` research

## Question

Issue #32 records that the in-pipeline `vaultspec-code-reviewer` agent
returned `APPROVE` twice on PR #28 (the storage layer landed as squash
`a4692fb`) while two external bots (`gemini-code-assist` and
`chatgpt-codex-connector`) found nine substantive correctness bugs. The
goal of this research pass is to (a) verify that the merged storage layer
on `main` actually addresses every one of the externally-reported issues,
(b) re-audit the layer for any further bugs the in-pipeline reviewer would
also miss, and (c) understand *why* the in-pipeline reviewer was blind to
the original class of bugs so the agent prompt can be hardened.

## Background

PR #28 introduced `src/aeat/adapters/persistence/storage/` (SQLite + SQLAlchemy 2.x + Alembic),
a public pydantic v2 record surface, three repositories, an engine
factory, a session helper, and a programmatic Alembic facade. The
external review history is captured on the PR comments thread:

- Round 1 (against commit `d80dcea`): six findings — SQLite
  `PRAGMA foreign_keys` not enabled, dead `AEAT_STORAGE_AUTO_MIGRATE`
  setting, missing CHECK on `portals.auth_method`, missing UNIQUE on
  `corpus_artifacts (year, modelo_id, file_path)`, `upsert` not actually
  upserting on natural keys, raw `IntegrityError` leaking out of the
  package boundary.
- Round 2 (against commit `cac3f09`): three findings — race in
  `get_engine` caching the engine before migrations finished,
  `migrations/env.py` building a new engine from ini config instead of
  reusing the injected one, hardcoded `"upsert"` label in
  `_flush_or_wrap` even though the helper is shared with delete paths.

All nine findings were addressed in `cac3f09` and the PR was squash-merged
as `a4692fb`. The retro question is whether the in-pipeline reviewer
checklist needs new entries to catch these classes of bugs in the future.

## Method

- Read `gh issue view 32` to get the canonical bug list.
- Read `gh pr view 28 --comments` and `gh pr diff 28` to confirm the
  external bots' raw findings and the fixes applied.
- Read every file under `src/aeat/adapters/persistence/storage/` and `migrations/` on `main`.
- Verify that the round-trip migration test, FK cascade test, CHECK
  rejection test, natural-key upsert test, integrity-error wrapping test,
  in-memory injected-engine test, and `aeat_storage_auto_migrate` test all
  exist and exercise the actual SQLite engine (not mocks).
- Run `just lint && just typecheck && just test && just hooks` against
  the worktree to confirm a green starting state.
- Grep for `logging.getLogger`, `# type: ignore`, bare `dict[str, Any]`
  / `: Any` annotations across `src/aeat/adapters/persistence/storage/`.
- Grep for cross-package imports of `aeat.adapters.persistence.storage._*` from outside the
  subpackage to verify public-API discipline.
- Read `.vaultspec/rules/agents/vaultspec-code-reviewer.md` and the
  associated `code-review.md` template to identify exactly which checklist
  items already exist and where the gaps are.

## Findings (verification of the externally-reported bugs)

Each of the nine externally-reported bugs is now fixed on `main`:

1. `src/aeat/adapters/persistence/storage/engine.py:46-65` installs a `connect` event listener
   that issues `PRAGMA foreign_keys=ON` for every SQLite connection.
2. `src/aeat/adapters/persistence/storage/engine.py:115-126` consults
   `resolved.aeat_storage_auto_migrate` and runs `upgrade_to_head` before
   publishing the engine to the cache; the setting is documented in
   `env/.env.example:64`.
3. `src/aeat/adapters/persistence/storage/_orm.py:56-61` declares the
   `ck_portals_auth_method` CHECK constraint, and
   `migrations/versions/0002_constraints.py:25-28` adds it via
   `batch_alter_table`.
4. `src/aeat/adapters/persistence/storage/_orm.py:91-98` declares the
   `uq_corpus_artifacts_identity` UNIQUE constraint, and
   `migrations/versions/0002_constraints.py:30-34` adds it via Alembic.
5. The three `upsert` methods in `src/aeat/adapters/persistence/storage/repository.py` look up
   the existing row by natural key when `record.id is None`
   (`identifier` for modelos and portals,
   `(year, modelo_id, file_path)` for corpus artifacts).
6. `src/aeat/adapters/persistence/storage/repository.py:25-38` wraps `IntegrityError` as
   `RepositoryError`; `repository.py:175-180` wraps the `ValueError` from
   the `PortalAuthMethod` decode.
7. `src/aeat/adapters/persistence/storage/engine.py:110-127` only writes `_engines[url]`
   *after* migrations complete, and disposes the engine on migration
   failure so a broken cache entry can never be observed.
8. `migrations/env.py:55-65` reuses the engine injected via
   `config.attributes["connection"]` and only falls back to
   `engine_from_config` for the `alembic` CLI path; the in-memory
   injected-engine test at `_test_constraints.py:233-244` covers this.
9. `src/aeat/adapters/persistence/storage/repository.py:38` interpolates the `kind` argument
   into the error message ("integrity violation during {kind}
   operation"), so the `delete` callers no longer get the hardcoded
   `"upsert"` text.

## Findings (re-audit pass against the project mandates)

- **Lint / typecheck / tests / hooks all green** on Windows in this
  worktree (`just lint`, `just typecheck`, `just test`, `just hooks`).
  The full pytest run reports `212 passed, 1 skipped, 9 deselected`,
  including every storage regression test added in round 2.
- No `logging.getLogger` calls — every storage module uses
  `aeat.core.logging.get_logger(__name__)`.
- No `# type: ignore` comments anywhere in `src/aeat/adapters/persistence/storage/`. The only
  `Any` annotation is a deliberate frozen-model mutation probe in
  `src/aeat/adapters/persistence/storage/_test_records.py:25`.
- All public records are pydantic v2 with `ConfigDict(strict=True,
  frozen=True)`; no public signature exposes a raw `dict[str, Any]`.
- All storage errors inherit from `aeat.core.errors.AeatError` via
  `StorageError`, and `MigrationError`/`RepositoryError` inherit from
  `StorageError` in turn.
- Every test carries `@pytest.mark.unit`; no `unittest` imports anywhere
  in the package; no mocks/patches/stubs in the regression tests — they
  all hit a real SQLite engine, including an in-memory variant for the
  Alembic injected-engine path.
- Public API discipline holds for runtime callers: no module outside
  `src/aeat/adapters/persistence/storage/` imports any private (`_`-prefixed) symbol.
- Public API discipline is **violated by two colocated test modules**:
  `src/aeat/adapters/persistence/storage/_test_repository.py:23` and
  `src/aeat/adapters/persistence/storage/_test_session.py:12` import `Base` from
  `aeat.adapters.persistence.storage._orm` and call `Base.metadata.create_all(engine)` to
  bootstrap the schema instead of using `upgrade_to_head` from the
  public surface. This is the same flavor of finding the LLM-client
  review surfaced as `public-api-001`.

## Findings (the in-pipeline reviewer prompt)

Reading `.vaultspec/rules/agents/vaultspec-code-reviewer.md`, the
existing checklist covers safety (crashes, leaks, deadlocks, FFI),
intent (plan compliance, drift), and quality (idioms, performance,
docs). It does **not** mention any of the following classes of bug,
and that maps directly onto the misses from rounds 1 and 2:

- **Driver-specific defaults.** SQLite ships with foreign keys disabled
  by default; PostgreSQL and MySQL do not. The reviewer prompt has no
  "for every database backend touched, list the defaults that differ
  from the production target and confirm they are explicitly enabled"
  step. Bug #1 falls out of this gap.
- **Dead settings.** The reviewer reads the diff but does not require
  that every newly declared setting field must have a grep-verified
  reader in the same diff. Bug #2 falls out of this gap.
- **Schema-level integrity constraints.** The reviewer checks that
  pydantic records are strict and frozen but does not require that
  closed catalogues have a CHECK constraint on the database column that
  stores them, or that natural keys have a UNIQUE constraint. Bugs #3
  and #4 fall out of this gap.
- **Natural-key upsert semantics.** "upsert" can mean three different
  things (PK-only, natural-key, ON CONFLICT clause). The reviewer prompt
  does not require the executor to spell out which semantics are
  intended for each repository, so the missing natural-key path on a
  fresh insert was invisible. Bug #5 falls out of this gap.
- **Exception-type leakage.** The reviewer checks that domain errors
  exist but does not require an explicit walk: for every public function
  that touches a library call, list the library exception types that
  call can raise and confirm each is wrapped before crossing the
  package boundary. Bug #6 falls out of this gap.
- **Cache-before-init lifecycle.** Singletons / factories that combine
  lazy initialization with caching have a publish-before-finish hazard.
  The reviewer does not require a "when is the value published vs.
  initialised, and what happens under concurrent callers and under init
  failure" walk. Bug #7 falls out of this gap.
- **Cross-file interaction.** `migrations_api.py` and `migrations/env.py`
  each look fine in isolation; the bug only exists in the seam between
  them (the engine injected on one side, ignored on the other). The
  reviewer prompt does not require an "interaction diff" pass that
  walks both entry points of every paired file change. Bug #8 falls out
  of this gap.
- **Helper text vs. helper scope.** Bug #9 (hardcoded `"upsert"` in a
  shared helper) is a low-severity but real-world hint that the
  reviewer's "language idioms" check does not extend to "does the error
  text match the actual call site," which a devil's-advocate second
  reviewer seeded with only the diff would have caught immediately.

## Decision implications

The merged storage layer on `main` is correct: every externally-reported
bug is fixed and the regression tests cover them. The audit document
will record one new fresh finding (LOW: test-only public-API leak on
`Base.metadata.create_all`) and propose explicit additions to the
in-pipeline reviewer prompt corresponding to each of the nine missed
classes above. No code fix is required on this branch — issue #32 is a
process retro, not a correctness retro.
