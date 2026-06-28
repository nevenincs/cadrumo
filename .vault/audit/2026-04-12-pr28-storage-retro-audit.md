---
tags:
  - '#audit'
  - '#pr28-storage-retro'
date: '2026-04-12'
modified: '2026-04-12'
related:
  - '[[2026-04-12-pr28-storage-retro-research]]'
  - '[[2026-04-12-data-storage-research]]'
---

# `pr28-storage-retro` Code Review

This audit re-reviews the merged `src/aeat/adapters/persistence/storage/` layer (PR #28,
squash-merged as `a4692fb`) against the project mandates listed in
`CLAUDE.md`, verifies that every bug the external bots flagged on PR #28
is actually fixed on `main`, and records the gaps in the in-pipeline
`vaultspec-code-reviewer` agent that allowed those bugs through twice.

The retro was driven by issue #32. No `CRITICAL` or `HIGH` findings were
identified on the merged layer. One `LOW` finding is recorded for
documentation. The substantive deliverable is the process-recommendation
section at the end.

## Verification Of Externally-Reported Bugs

Each of the nine bugs the external bots flagged on PR #28 is fixed on
`main`. The verification table below records the original bug, the file
and line range that proves the fix, and whether the in-pipeline reviewer
checklist as currently written would have caught the original.

retro-001 | RESOLVED | SQLite `PRAGMA foreign_keys=ON` is now enabled
The connect-event listener at `src/aeat/adapters/persistence/storage/engine.py:46-65` issues
`PRAGMA foreign_keys=ON` for every new SQLite connection. The cascade is
covered end-to-end by `src/aeat/adapters/persistence/storage/_test_constraints.py:51-75`,
which inserts a `corpus_artifact`, deletes the parent `modelo`, and
asserts the artifact row is gone. *In-pipeline gap:* the reviewer prompt
has no driver-defaults check.

retro-002 | RESOLVED | `AEAT_STORAGE_AUTO_MIGRATE` is now consulted
`src/aeat/adapters/persistence/storage/engine.py:115-126` reads `aeat_storage_auto_migrate`
from the resolved settings and runs `upgrade_to_head` against the new
engine *before* publishing it to the URL-keyed cache.
`src/aeat/adapters/persistence/storage/_test_constraints.py:174-188` proves the auto-migrate
path produces the migrated schema. The setting is documented in
`env/.env.example:64`. *In-pipeline gap:* the reviewer prompt does not
require new settings to have a grep-verified reader in the same diff.

retro-003 | RESOLVED | `portals.auth_method` has a CHECK constraint
`src/aeat/adapters/persistence/storage/_orm.py:56-61` declares the `ck_portals_auth_method`
constraint on the ORM table, and
`migrations/versions/0002_constraints.py:25-28` adds it via
`batch_alter_table`. `src/aeat/adapters/persistence/storage/_test_constraints.py:78-95`
inserts a raw row with `auth_method='totally-bogus'` and asserts the
SQLite check fires. *In-pipeline gap:* the reviewer prompt does not
require closed catalogues to have a database-level CHECK constraint.

retro-004 | RESOLVED | `corpus_artifacts (year, modelo_id, file_path)` is unique
`src/aeat/adapters/persistence/storage/_orm.py:91-98` declares the
`uq_corpus_artifacts_identity` constraint, and
`migrations/versions/0002_constraints.py:30-34` adds it via Alembic.
`src/aeat/adapters/persistence/storage/_test_constraints.py:98-136` exercises the natural-key
upsert path on a duplicate. *In-pipeline gap:* the reviewer prompt does
not require natural keys to have a UNIQUE constraint.

retro-005 | RESOLVED | `upsert` is now a true natural-key upsert
The three repositories at `src/aeat/adapters/persistence/storage/repository.py:94-111`,
`:138-164`, and `:204-236` look up the existing row by natural key when
`record.id is None` and update in place if found. The natural-key
behavior is covered by `_test_constraints.py:139-151` (modelo) and
`_test_constraints.py:98-136` (corpus artifact). *In-pipeline gap:* the
reviewer prompt does not require the executor to spell out the intended
upsert semantics (PK only, natural key, or `ON CONFLICT`) per repository.

retro-006 | RESOLVED | `IntegrityError` is wrapped at the boundary
`src/aeat/adapters/persistence/storage/repository.py:25-38` (`_flush_or_wrap`) flushes the
session and converts `sqlalchemy.exc.IntegrityError` into
`RepositoryError`. Every mutation path on every repository goes through
this helper. The `PortalAuthMethod` decode at
`src/aeat/adapters/persistence/storage/repository.py:175-180` likewise wraps `ValueError` as
`RepositoryError`. The orphan-FK case is covered by
`_test_constraints.py:154-170`; the legacy-row decode case is covered
by `_test_constraints.py:191-230`. *In-pipeline gap:* the reviewer
prompt does not require an explicit walk of "for every public function
that touches a library call, name the exception types the library can
raise and verify each is wrapped."

retro-007 | RESOLVED | engine cache no longer publishes a half-built engine
`src/aeat/adapters/persistence/storage/engine.py:110-127` resolves the URL under `_lock`,
checks the cache, creates and migrates the engine, and only writes
`_engines[url]` *after* `upgrade_to_head` returns. On migration failure
the engine is disposed before the lock is released, so a broken cache
entry can never be observed. The cached-before-migration race is gone.
*In-pipeline gap:* the reviewer prompt does not require a "publish vs.
initialize order under concurrent callers and under init failure"
walk-through for new singletons / factories.

retro-008 | RESOLVED | `migrations/env.py` reuses the injected engine
`src/aeat/adapters/persistence/storage/migrations_api.py:26-40` injects the caller's engine
via `config.attributes["connection"]`, and `migrations/env.py:55-65`
prefers that engine over `engine_from_config` whenever it is present.
The `sqlite:///:memory:` regression test at
`_test_constraints.py:233-244` proves the in-memory case works.
*In-pipeline gap:* the reviewer prompt does not require an "interaction
diff" pass over paired files where each file looks correct in isolation
but the seam between them is the actual contract.

retro-009 | RESOLVED | `_flush_or_wrap` error text now reflects the caller
`src/aeat/adapters/persistence/storage/repository.py:38` interpolates the `kind` argument
into the message ("integrity violation during {kind} operation"), so
`delete` paths no longer report `"upsert"`. The label is plumbed through
on every call site. *In-pipeline gap:* the reviewer prompt's "language
idioms" check does not extend to "shared helper messages must reflect
the actual caller scope."

## Fresh Findings

All fresh findings on the merged layer are LOW or below.

public-api-001 | LOW | Colocated tests bootstrap schema via `Base.metadata.create_all`
`src/aeat/adapters/persistence/storage/_test_repository.py:23-30` and
`src/aeat/adapters/persistence/storage/_test_session.py:12-25` import the private `Base`
mapper from `aeat.adapters.persistence.storage._orm` and call `Base.metadata.create_all` to
seed the schema. Runtime callers comply with the public-API discipline
declared in `src/aeat/adapters/persistence/storage/__init__.py`, but these two test modules
violate it the same way the LLM-client review surfaced as
`public-api-001`. The functional impact is zero today (the metadata is
the same shape as the migrated schema), but it lets the test suite
diverge from the migration path that production actually exercises.
*Fix (out of scope for this branch):* replace the
`Base.metadata.create_all(engine)` calls with `upgrade_to_head(engine)`
from the public surface, the same pattern already used in
`_test_constraints.py:44-48`. Filed as a follow-up — not shipped here
because issue #32 is a process retro and the executing-team rule is
"minimal, targeted fixes only."

encoding-001 | INFO | Text columns are stored without explicit NFC normalization
`src/aeat/adapters/persistence/storage/_orm.py` declares plain `String(...)` columns for
`identifier`, `name`, `label`, `base_url`, `file_path`, `source_url`,
and `sha256`. The trilingual contract in `CLAUDE.md` calls out NFC as
the canonical Unicode form for cross-language text, but no normalization
is enforced at the storage boundary. This is acceptable for now because
the columns flagged as translatable carry inline `TODO(#20)` markers in
`_orm.py:40` and `_orm.py:71` that hand off to issue #20, which owns
the trilingual primitive and will define the boundary contract. Logged
here so the issue #20 owner can pick it up rather than rediscover it.

joined-load-001 | INFO | `relationship(..., lazy="joined")` is the default for portal/artifact reads
`src/aeat/adapters/persistence/storage/_orm.py:74` and `_orm.py:111` declare `lazy="joined"`
on the `portals.modelo` and `corpus_artifacts.modelo` relationships.
This eagerly issues a JOIN on every read and is fine at the current
data volume (a handful of modelos and portals) but is worth re-examining
once `corpus_artifacts` grows past a few hundred rows. Not a bug today.

datetime-tz-001 | LOW | `CorpusArtifactRecord.fetched_at` accepts naive datetimes
`src/aeat/adapters/persistence/storage/records.py:92` declares `fetched_at: datetime` with no
timezone constraint. The column is stored as `DateTime(timezone=True)`
in `_orm.py:109` and the field docstring says "UTC", but pydantic v2
`strict=True` rejects coercion, not naive datetimes — so a caller can
construct `CorpusArtifactRecord(..., fetched_at=datetime(2026, 4, 12))`
without `tzinfo` and the value will be persisted and round-tripped
under SQLite as a naive timestamp, silently violating the UTC contract.
Surfaced by the independent local review pass. *Fix (out of scope for
this branch):* swap the annotation to `pydantic.AwareDatetime`, or add
a `field_validator` that rejects `tzinfo is None`. Filed as a
follow-up issue rather than fixed here because the executing-team rule
on this branch is "minimal, targeted fixes, do not change the public
API surface other branches stub against," and tightening the field
validation is observable to callers.

private-import-001 | INFO | `migrations/env.py` reaches into `aeat.adapters.persistence.storage.engine._ensure_sqlite_parent`
`migrations/env.py:17` imports the underscore-private helper
`_ensure_sqlite_parent` from `aeat.adapters.persistence.storage.engine` so the Alembic
environment can create the SQLite parent directory before opening a
connection. The Rule Verification grep below records "no runtime
caller imports `aeat.adapters.persistence.storage._*`" — that statement is true for
`src/aeat/` runtime code, but the Alembic environment file at
repo-root `migrations/env.py` is technically outside the package and
*does* reach a private symbol. Acceptable for now (env.py is the
package's own glue, not a third-party caller), but worth recording so
it is not rediscovered as a finding on a future audit. *Possible fix:*
re-export `ensure_sqlite_parent` (no underscore) from
`aeat.adapters.persistence.storage` as part of the migration glue surface.

## Rule Verification

- **`src/aeat/`-only layout:** PASS. Every storage module lives under
  `src/aeat/adapters/persistence/storage/`.
- **Public API discipline (runtime callers):** PASS for `src/aeat/`
  runtime code. Grep for `aeat\.storage\._` from outside the package
  returns zero matches in runtime code; the only hits are the two
  colocated tests recorded in `public-api-001` above and the Alembic
  glue at `migrations/env.py:17`, recorded as `private-import-001`
  below. The Alembic env file is the storage package's own glue, not a
  third-party caller, so this is logged as INFO rather than a
  discipline violation.
- **Pydantic v2 mandate:** PASS. Every public record is a pydantic v2
  model with `ConfigDict(strict=True, frozen=True)` via the shared
  `_StrictFrozen` base in `src/aeat/adapters/persistence/storage/records.py:33-36`.
- **Errors inherit from `aeat.core.errors.AeatError`:** PASS. The full
  hierarchy is `AeatError → StorageError → {MigrationError,
  RepositoryError}` in `src/aeat/adapters/persistence/storage/errors.py`.
- **Logging via `aeat.core.logging.get_logger(__name__)`:** PASS. Grep for
  `logging.getLogger` in `src/aeat/adapters/persistence/storage/` returns zero matches.
- **No bare `dict[str, Any]` / `: Any` in public signatures:** PASS.
  The single `Any` annotation in `_test_records.py:25` is a deliberate
  frozen-model mutation probe, not a public signature.
- **No `# type: ignore` comments:** PASS. Grep returns zero matches in
  the storage subpackage.
- **Tests use pytest only, every test marked, no mocks/patches/stubs in
  live tests:** PASS. Every test in `src/aeat/adapters/persistence/storage/` carries
  `@pytest.mark.unit`; no `unittest` imports anywhere; the regression
  tests all hit a real SQLite engine, including the `sqlite:///:memory:`
  case for the Alembic injected-engine path.
- **Migration round-trip:** PASS. `round_trip_migrations` (head → base →
  head) is exercised by `_test_constraints.py:247-258`, which also
  asserts the `uq_corpus_artifacts_identity` constraint survives the
  cycle.
- **`just lint && just typecheck && just test && just hooks` green on
  Windows:** PASS. The full pytest run reports `212 passed, 1 skipped,
  9 deselected` in this worktree on `2026-04-12`.

## Reviewed Files

- All files under `src/aeat/adapters/persistence/storage/`: `__init__.py`, `_orm.py`,
  `engine.py`, `errors.py`, `migrations_api.py`, `records.py`,
  `repository.py`, `session.py`, `test_smoke.py`, `_test_constraints.py`,
  `_test_engine.py`, `_test_migrations.py`, `_test_records.py`,
  `_test_repository.py`, `_test_session.py`.
- All Alembic files: `alembic.ini`, `migrations/env.py`,
  `migrations/versions/0001_initial.py`,
  `migrations/versions/0002_constraints.py`.
- Settings alignment: `src/aeat/config.py` (`aeat_database_url`,
  `aeat_storage_auto_migrate`) and `env/.env.example:60-64`.
- The in-pipeline reviewer agent definition at
  `.vaultspec/rules/agents/vaultspec-code-reviewer.md` and the review
  template at `.vaultspec/rules/templates/code-review.md`.
- PR history via `gh issue view 32`, `gh pr view 28 --comments`, and
  `gh pr diff 28`.

## Process Recommendations For The In-Pipeline Reviewer

These recommendations are the primary deliverable of issue #32. Each
maps onto one or more of the nine bugs the external bots caught and
the in-pipeline reviewer missed. They are scoped to changes the
reviewer agent can make against the diff alone — they do not require
the agent to run the test suite, although recommendation `R-08` argues
that it should.

R-01 | Driver-defaults sweep
For every new SQL backend touched in the diff, the reviewer must list
the defaults that differ from the production target backend (e.g.
SQLite vs. PostgreSQL: foreign keys disabled by default, no concurrent
writers, type affinities are advisory) and confirm each one that
matters is explicitly overridden in code. This single check would have
caught retro-001 on round 1.

R-02 | Dead-settings sweep
Any new field on `aeat.core.config.Settings` must have a grep-verified
reader inside the same diff. The reviewer must produce that grep
result in the report; an empty result is a `HIGH` finding. This would
have caught retro-002 on round 1.

R-03 | Closed-catalogue CHECK constraints with single source of truth
Any field whose pydantic type is a `StrEnum` or other closed catalogue
must have a database-level CHECK constraint on the column that stores
it, mirrored in the latest Alembic revision. The reviewer must confirm
both the ORM mapper and the migration include the constraint *and*
that the catalogue values are not duplicated as string literals across
the pydantic enum, the ORM `CheckConstraint`, and the Alembic
`create_check_constraint` call. Today
`src/aeat/adapters/persistence/storage/_orm.py:58` and
`migrations/versions/0002_constraints.py:21` each spell out the four
auth-method values independently — if `PortalAuthMethod` grows a fifth
value, three places drift in lockstep. The reviewer must demand a
single source of truth (e.g. `tuple(PortalAuthMethod)` consumed by
both the ORM and migration). This would have caught retro-003 and
prevents a future drift bug.

R-04 | Natural-key UNIQUE constraints
Any "natural key" tuple referenced in repository code (typically the
columns the upsert path uses to look up an existing row) must have a
UNIQUE constraint declared at both the ORM and migration layers. This
would have caught retro-004.

R-05 | Upsert semantics declaration
For every repository that exposes an `upsert` method, the reviewer
must require the diff or its plan to spell out which semantics are
intended (PK-only update, natural-key resolve-then-update, or backend
`ON CONFLICT`) and verify the implementation matches. This would have
caught retro-005.

R-06 | Exception-type leakage walk
For every public function that touches a third-party library call, the
reviewer must enumerate the exception types that library call can
raise and verify each is either wrapped into the package's domain
error hierarchy or explicitly re-exposed. This applies to SQLAlchemy,
httpx, Playwright, Alembic, Anthropic SDK, and Google clients. This
would have caught retro-006.

R-07 | Lazy-singleton lifecycle walk
For every new singleton, factory, or cache that combines lazy
initialization with a stored value, the reviewer must walk the order
of (a) acquire lock, (b) check cache, (c) create value, (d) initialize
value, (e) publish value, (f) release lock — and confirm what happens
under concurrent callers and under an exception in step (d). This
would have caught retro-007.

R-08 | Interaction-diff pass for paired files
For every pair of new or modified files where one calls into the other
across a contract (e.g. `migrations_api.py` ↔ `migrations/env.py`,
`runner.py` ↔ `wire.py`, an adapter ↔ its registry), the reviewer must
walk both entry points and verify the shared invariant — not just read
each file in isolation. The reviewer report must list every paired
contract it checked. This would have caught retro-008.

R-09 | Helper-message scope check
Shared helpers that take a "kind" / "operation" / "label" argument must
interpolate that argument into every user-facing message. The reviewer
must scan for hardcoded operation names inside such helpers. This is
the catch for retro-009.

R-10 | Devil's-advocate second pass
Add a lightweight second reviewer agent that is seeded with *only* the
PR diff (no plan, no ADR, no checklist beyond a one-liner: "what
breaks here under production load?") and is run *before* the primary
reviewer's `APPROVE`. The second reviewer's findings are treated as
evidence the primary reviewer must explicitly address — not as a
veto, but as a forcing function against confirmation bias. Issue #32's
analysis section explicitly proposes this as item 6.

R-11 | Reviewer must run lint, typecheck, tests, hooks
The reviewer agent today is read-only: it reads code and writes a
report. It does not actually execute `just lint && just typecheck &&
just test && just hooks`. Round 1 of PR #28 would have failed at least
the auto-migrate test if the reviewer had been required to run the
suite. Recommendation: change the reviewer's `mode` from `read-only` to
allow `Bash`, and require the report to embed the verbatim final lines
of each of the four commands. This is also the easiest single change
to ship — it does not require any prompt changes.

R-12 | Per-domain reviewer subagents (medium-term)
The current single reviewer is a generalist. The bugs on PR #28 cluster
in three domains — SQL/migrations, error-taxonomy/boundaries, and
concurrency/lifecycle — and the prompts that would catch them are very
different from the prompts a browser-automation review or an LLM-client
review would need. Recommendation: explore splitting the reviewer into
per-domain personas (`storage-reviewer`, `auth-reviewer`,
`browser-reviewer`, `llm-reviewer`) that share the safety/intent core
but layer domain-specific checklists on top. Track this as a follow-up
to issue #32; not in scope for the immediate prompt update.

## Final Status

PASS. The merged storage layer on `main` is correct, every external
finding from PR #28 is closed, the regression coverage is real (no
mocks, hits a real SQLite engine), and `just lint && just typecheck &&
just test && just hooks` are green on Windows in this worktree.

The substantive output of this audit is the twelve recommendations
above for the in-pipeline `vaultspec-code-reviewer` agent. The
acceptance criterion in issue #32 — "the agent's checklist explicitly
covers the six round-1 failure modes" — is satisfied by R-01 through
R-06 and R-09; R-07 and R-08 cover the round-2 misses; R-10, R-11, and
R-12 are forward-looking process changes that issue #32 itself
requested.
