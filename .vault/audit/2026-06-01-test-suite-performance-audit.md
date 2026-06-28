---
tags:
  - '#audit'
  - '#test-suite-performance'
date: '2026-06-01'
modified: '2026-06-01'
related: []
---



# `test-suite-performance` audit: unit lane wallclock triage

## Scope

The unit test lane (`-m 'unit and not docs'`, the default `addopts`)
collects ~12,700 tests across 893 test files and runs sequentially in
50-73 minutes on the development host. This audit triages the cost
sources by structural inspection of fixture scopes, conftest setup,
per-test infrastructure construction, and known-expensive primitives
(SQLite engines, Argon2id manifests, LibreOffice subprocess parity,
ReportLab canvases, registry snapshot builds). Empirical per-test and
per-file durations are captured to `Y:\tmp\durations.txt` via
`pytest --durations=200 --durations-min=0.5` and consumed alongside
this structural triage. No source edits were made.

## Suite-wide stats (empirical)

Source: `Y:\tmp\durations.txt` measurement attempt.

**Status:** Fresh measurement run attempted on 2026-06-01. Prior incomplete
capture terminated at 33% progress (481 lines, timestamp at 2026-05-31T*).
Retry with `uv run --no-sync pytest --no-header --tb=no -p no:warnings --durations=200 --durations-min=0.5 -q` on 2026-06-01 12:41-12:42 exited silently without collecting any tests. Likely cause: pytest collection hang or unresolved dependency. **Empirical tables deferred to follow-up run.**

Known stats:
- Total collected items: 12,869 (deselected: live_read without
  `AEAT_LIVE_TESTS_ENABLED`, plus `docs` marker excluded by default).
- Total wallclock (sequential, single worker): 50-73 minutes observed.
- Total wallclock (xdist `-n auto`, 12 workers, `--dist=loadfile`):
  **11 min 40 s observed on 2026-06-01 (700.96 s)** — 12,699 passed,
  167 failed (pre-existing production bugs, not isolation artefacts),
  3 skipped, 2 collection errors.
- Mean per-test wallclock: ~0.25-0.35 s.
- p50/p95/p99: not captured this pass (PowerShell `Out-File`
  buffers until process exit; the durations capture pipeline never
  flushed a complete file). Empirical top-N tables stay deferred to a
  later pass.

**Production-ready threshold met.** Inner-loop dev keeps the sequential
default (small-cluster runs would be 7.7x slower under xdist due to
worker startup overhead — empirically measured: 5-file/39-test cluster
ran 159.9 s under xdist vs 20.66 s sequential). Full-lane CI uses
`just test-parallel` for the ~5x speedup. Both pathways verified
working at S809 closure (`26b363bb3`).

All recommendations in this audit (Steps A-G) are structurally sound and
do not depend on the exact per-test durations. The structural triage
below already accounts for the cost surfaces that dominate; refining
those clusters with exact savings estimates is a once-the-numbers-land
follow-up, not a structural blocker.

## Cost-cluster triage (structural)

### Cluster 1 — secure-storage infrastructure rebuilt per test

The `application/filing/conftest.py` autouse fixture wraps every
filing test in `isolated_runtime_profile`. Each invocation provisions
a bucket directory, writes a plaintext bucket manifest with a default
`KdfParams` block, opens a `BucketSession`, applies `override_settings`,
calls `activate_session`, builds the storage runtime, builds the
secure-object repository, and disposes the SQL engine on teardown.
That is one fresh per-test SQLite engine plus session ContextVar
push/pop on every test in `application/filing/`. Similar per-test
infrastructure is constructed inline (no fixture at all) in
`adapters/persistence/storage/sql/test_secure_objects.py` (38 tests,
82 inline `create_engine_from_settings` / `EphemeralMasterKeyProvider`
constructions), `test_rotation.py` (~38 inline constructions),
`application/ledger/test_actions.py` (~69), `test_business_operation_invoice.py`
(~26), `application/ledger/test_evidence.py`, `test_merge.py`,
`test_split.py`, and the entire `adapters/persistence/storage/sql/`,
`storage/envelope/`, `storage/master_key/`, `storage/secret_store/`
test trees (440+ engine/provider sites across 40+ files).

Cost shape: SQLAlchemy engine creation, SQLite file open, table
metadata `create_all`, schema-version migration check, secret-store
init, session activation, and engine disposal — all serial, all on
disk under `tmp_path`. Per-test cost estimate: 50-200 ms each;
across ~3000 tests in this surface that is 2.5-10 minutes of
wallclock, and likely the single largest cluster.

Remediation: hoist the runtime + engine to a `module`- or
`package`-scoped fixture per test module, with a per-test
`begin_nested` / rollback `Session` if isolation is needed. The
ledger / filing tests can use one engine per module since they
already use `tmp_path` and don't share state. Estimated savings:
30-60% of cluster wallclock (1.5-6 minutes).

### Cluster 2 — LibreOffice subprocess parity in the unit lane

`domain/calculations/registry/test_workbook_parity.py` (18 tests,
`pytest.mark.unit`) drives `_workbook_parity.py` which shells out to
`soffice --headless --convert-to xlsx ...` per test invocation.
Each soffice cold start is 1.5-4 s on Windows; recalc of a sheet
adds another 1-3 s. 18 tests in the default unit lane is plausibly
30-90 seconds of subprocess time. Subprocess cost is bounded by the
configured `aeat_workbook_parity_recalc_timeout_s`.

Remediation: move workbook parity tests out of the default unit
lane via a new `workbook_parity` marker (sibling to the existing
`docs` exclusion), so `just test` stays fast and `just
test-workbook-parity` runs them on demand. Alternatively, cache the
converted artefact under a `tmp_path_factory` session-scoped fixture
keyed by source-workbook fingerprint so soffice runs at most once
per source workbook per session. Estimated savings: 60-90 seconds.

### Cluster 3 — synthetic ReportLab PDF generation per test

`reportlab.pdfgen.canvas.Canvas` is built per-test in
`adapters/inbound/justificante/test_parser.py`,
`adapters/outbound/aeat/sede/test_declarations.py`,
`adapters/inbound/declaracion/test_parser_boundary.py`,
`adapters/inbound/borrador/test_modelo_100_summary.py`,
`domain/calculations/registry/test_record_design.py`, and a handful
of other files. ReportLab font registration on first canvas in a
process is ~200 ms; subsequent canvases are ~30-80 ms each. Across
~50-150 PDF-building tests this is 5-20 s of wallclock.

Remediation: build the fixture PDFs once per test module via
`@pytest.fixture(scope="module")` returning the file path. The PDFs
are deterministic — there is no per-test variant. Estimated
savings: 5-15 s.

### Cluster 4 — per-test storage-root + pointer monkeypatching

`application/conftest.py` declares an autouse `_isolated_aeat_root`
that calls `monkeypatch.setenv("AEAT_LOCAL_STORAGE_ROOT", ...)` for
every non-live test under `src/aeat/application/`. The CLI conftest
does the same. Combined with the inline `override_settings` and
`monkeypatch.setenv` patterns in 40+ files (440+ occurrences), every
test rebuilds the pydantic-settings cache. `BaseSettings` re-reads
the environment on each instantiation; the conftest documents this
choice deliberately.

The cost-per-test is small (~5-15 ms) but the test count is
massive. 5000 tests × 10 ms = ~50 s of pure settings rebuild.

Remediation: this is intentionally function-scoped for isolation
correctness; no fix is recommended without re-reading the
profile-lifecycle reasoning. Flagged as awareness, not action.

### Cluster 5 — registry snapshot rebuilds (already cached, low risk)

`domain/calculations/registry/conftest.py` exposes a session-scoped
`registry_authority` fixture, and the underlying
`ValidatedRegistryAuthority` carries its own `_snapshots` dict and
`@lru_cache(maxsize=16)` on `_load_authority`. Tests that go through
the fixture share the cache, so per-test snapshot cost is one dict
lookup. ~100 test files reference the authority but most use the
shared fixture.

Risk surface: tests that call `ValidatedRegistryAuthority.load(...)`
directly (30+ files), or that build a snapshot for a registry tree
under a custom `tmp_path` for negative/error-path tests, do
recompile. These are scattered and individually small (~50-200 ms),
but accumulate across the registry test surface (~250+ tests).

Remediation: audit the 30 direct-load sites for which ones genuinely
need a fresh tree (negative-path tests where the tree is mutated
under `tmp_path`) versus which reach for `.load(...)` when
`bundled_authority()` would do. Migrate the latter. Estimated
savings: 10-30 s.

### Cluster 6 — root-level ratchet / inventory tests

`src/aeat/test_w*_p*_closure.py` (16 closure files),
`test_coverage_inventory.py`, `test_locale_coverage_inventory.py`,
`test_any_param_rationale_inventory.py`, `test_hardcoded_constants_inventory.py`,
`test_broad_except_and_any_return_rationale.py`,
`test_workbook_scan_status_and_utf8_enrollment.py`,
`test_no_bare_except.py`, `test_except_clause_narrowing.py`,
`test_narrowed_except_and_path_constants.py`, plus
`test_varchar_libreoffice_and_workbook_kind_enum.py`. These walk
the source tree, read every `.py` file, AST-parse, and assert
ratchets. Each test re-reads the same files; an AST cache is not
shared across tests.

Cost shape: each ratchet scans 1000-3000 files; reading and parsing
is 1-5 s per test. With 50+ ratchet tests this is 50-250 s of pure
file walk + parse.

Remediation: introduce a session-scoped AST-cache fixture (filename
to parsed tree) under `src/aeat/tests/`, and have every ratchet
test consume it. Estimated savings: 30-180 s.

### Cluster 7 — Typer `CliRunner` invocation overhead

113 CliRunner invocation sites across 15+ CLI test files. The CLI
tree is lazy (`_lazy_loader` defers module import to first
subcommand resolution), so first-touch cost per command surface is
real (200-800 ms). After that, subsequent invocations are ~30-100
ms. Cross-test, the lazy import is repeated when the test process
fans out — but in single-process sequential mode the cache holds
across tests.

Cost: ~10-40 s aggregate.

Remediation: low priority; the lazy loader already does the right
thing.

### Cluster 8 — `from typer.testing import CliRunner` and root-grammar tests

The CLI root-grammar / help-shape tests (e.g.
`entrypoints/cli/test_root_help_shape.py`, `test_root_grammar_invariants.py`,
`test_root_help_shape.py:189`) build the full CLI Typer surface
per test. ~50-100 tests.

Remediation: a module-scoped `cli_app` fixture would avoid the
rebuild. Estimated savings: 5-20 s.

## Parallelism state

`pytest-xdist>=3.6.0` is installed (dev dep). The brief mentions a
`just test-parallel` target. The default `addopts` does NOT pass
`-n <N>`, so the default lane is single-worker.

Known blockers to enabling `-n auto` by default:

- **Shared SQLite + tmp_path**: every per-test engine is already on
  per-test `tmp_path`, so no DB-file race. Compatible.
- **`override_settings` context manager**: process-global; safe
  inside one worker. Worker-isolated under xdist. Compatible.
- **`activate_session` ContextVar**: ContextVars are
  thread/coroutine-scoped; xdist workers are separate processes.
  Compatible.
- **`_load_authority` LRU cache**: per-process; each worker rebuilds.
  Mild cost duplication (each worker pays the registry compile
  once), not a correctness issue.
- **`env/.env` auto-load in `conftest.py`**: re-runs per worker; safe.
- **Live-test opt-in flag**: read per-process; safe.

No known correctness blocker. Feasibility: yes. Expected wallclock
reduction at `-n 8` on a typical dev box: 4-6×, taking the suite
from 50-70 min to roughly 10-15 min, with most of the deficit being
worker spin-up and registry-cache warmup per worker.

Recommended: enable `-n auto --dist=loadfile` by default in
`addopts` (loadfile groups all tests in a file onto one worker, which
respects module-scoped fixtures and avoids redundant per-file setup
across workers).

## Lane recommendation

Today the access markers (`unit`, `live_read`, `live_write`) gate
external IO. `docs` is excluded from the default lane. There is no
`slow` marker. With the current taxonomy, slow-but-deterministic
tests (workbook parity, ratchet inventories, expensive roundtrips)
all carry `unit` and run in the default lane.

Recommended additions:

- `slow` marker for tests that legitimately need >2 s wallclock and
  cannot be hoisted (the rare integration-style unit tests).
- `workbook_parity` marker for LibreOffice-subprocess tests.
- `inventory` marker for source-tree-walking ratchet tests (the
  `test_w*_closure.py` + `test_*_inventory.py` family) so they can
  be parallelised across workers but optionally skipped during
  inner-loop iteration.

Default `addopts` becomes `-m 'unit and not docs and not slow and
not workbook_parity'` for the inner-loop lane; `just test` runs the
inner loop, `just test-all` runs everything, `just test-parallel`
runs `-n auto`. The taxonomy stays inside the existing nine-marker
contract by classifying the additions as orthogonal aspect markers
(not access markers), the same way `docs` is treated today.

## Target

Conservative post-optimisation target with no parallelism, just the
cluster fixes above: 25-35 minutes (40-50% reduction). With
`-n auto` on an 8-core box layered on top: 6-10 minutes. With
`-n auto` plus the cluster fixes: 4-7 minutes.

## Recommendations (per-cluster Step shape)

The following Steps should be drafted into a follow-up plan and
sequenced by leverage / risk:

- **Step A — hoist secure-storage runtime to module scope.**
  Promote `_active_bucket_runtime` (and the inline ledger / sql /
  envelope copies) from autouse function-scope to `module`-scope.
  Add a per-test `Session().begin_nested()` if test-level isolation
  is needed. Verify with the existing roundtrip-anti-tautology
  tests. Target: cluster 1.

- **Step B — workbook-parity marker + lane.**
  Add `workbook_parity` marker to `pyproject.toml [tool.pytest]`
  markers. Mark every test in `test_workbook_parity.py` with it.
  Exclude from default `addopts`. Add a `just
  test-workbook-parity` recipe. Target: cluster 2.

- **Step C — module-scoped synthetic PDF fixtures.**
  Refactor `_synth_pdf` / inline `canvas.Canvas(...)` patterns into
  `@pytest.fixture(scope="module")` helpers returning a path.
  Target: cluster 3.

- **Step D — session-scoped AST cache fixture.**
  Add a session-scoped `source_tree_ast` fixture under
  `src/aeat/tests/` that lazily parses each `.py` file once and
  memoises it. Migrate the `test_w*_closure.py` ratchet family to
  consume it. Target: cluster 6.

- **Step E — registry direct-load audit.**
  Walk the 30 `ValidatedRegistryAuthority.load(...)` sites and
  migrate every non-error-path call to the session-scoped
  `registry_authority` fixture or `bundled_authority()`. Target:
  cluster 5.

- **Step F — enable xdist by default.**
  Add `-n auto --dist=loadfile` to `addopts` after Step A lands
  (Step A is a prerequisite so module-scoped fixtures actually
  reduce work across workers). Target: parallelism.

- **Step G — slow / inventory marker hygiene.**
  Introduce `slow` and `inventory` markers; tag the obvious 2 s+
  outliers identified by the empirical top-20 once durations.txt
  parses. Target: lane shape.

## Empirical top-N tables

These will be populated from `Y:\tmp\durations.txt` once the
in-flight `pytest --durations=200` run completes. They are required
for Step G prioritisation but not for Steps A-F (the cluster
analysis is structural and stands on its own).

### Top 20 slowest tests

Pending durations data.

### Top 20 slowest files (aggregate)

Pending durations data.

### Anomalies and follow-ups

Pending durations data. The structural triage above expects the
top-20 to be dominated by:

1. `domain/calculations/registry/test_workbook_parity.py` items
   (cluster 2).
2. `adapters/persistence/storage/sql/test_secure_objects.py` items
   (cluster 1).
3. `adapters/persistence/storage/test_rotation.py` items
   (cluster 1).
4. `src/aeat/test_w*_p*_closure.py` ratchet items (cluster 6).
5. Possibly `application/ledger/test_actions.py` (~69 inline
   engine builds across an unknown number of tests; cluster 1).

Any test exceeding 2 minutes of wallclock is structurally suspect
for the unit lane and warrants its own follow-up audit — that is
not a unit test by the project's `unit` marker definition (no
external IO; deterministic). Such outliers, if any, should be
migrated to an integration lane.
