# Where a development run writes

Every `dev/` command that measures something — quality, health, performance,
conformance, coverage — produces bytes that are not source. This document is
the canonical inventory of where those bytes land, and of the one rule that
governs them.

## The rule

**`dev/` holds the harness. It never holds the harness's output.**

A run's output goes to `.logs/`, which is git-ignored, reclaimed by
`just clean-apply`, and never maintained by hand. Nothing in the product or the
tooling is entitled to read a file back out of it: the boundary is one-way, and
that is exactly what makes reclaiming the whole root safe.

The distinction that matters is not "generated vs. hand-written", it is
**source vs. output**:

| | Source | Run output |
|---|---|---|
| Read by | the next run | nothing |
| Losing it | loses work | costs one re-run |
| Lives in | the tree, tracked | `.logs/`, reclaimed |
| Examples | authored ledgers, pinned matrices, reviewed queues | coverage reports, findings dumps, captured stderr |

A measurement that lands beside its own harness gets none of what `.logs/`
provides: no clean reclaims it, no run identity separates two measurements of
the same tree, and it needs a `.gitignore` entry to stay out of commits. That
is not a hypothetical — the terminology coverage report did exactly this, its
recipe called it "committed" while `.gitignore` hid it, and the contradiction
survived because nothing was checking.

`dev/tests/test_dev_tree_holds_no_run_output.py` is now what checks. Every path
under `dev/` that a production module resolves must be declared there with the
reason it is a source; an undeclared one fails the gate naming the module, the
line and the path.

## The output roots

| Root | Holds | Reclaimed by | Allocated through |
|---|---|---|---|
| `.logs/<family>/<date>/<run-id>/` | per-run evidence: logs, reports, captured payloads | `just clean-apply`, whole root | `dev.test_runs.paths.allocate_run_directory` |
| `.logs/test-runs/` | live pytest run directories | `dev.env.temp_reaper`, by owning-PID liveness, at any age | `dev.test_runs.logging` |
| `.cache/<name>/` | derived caches: registry pickles, record designs, corpus text | `just clean-apply` | `dev.cache_root.dev_cache_dir` (`CADRUMO_DEV_CACHE_ROOT` relocates) |
| `var/storage/` | the dev loop's application storage | not scratch; the worktree section owns it | `CADRUMO_LOCAL_STORAGE_ROOT`, set by the justfile |
| `var/<family>/` | packaging build scratch, runtime-compatibility runs, release logs | the packaging sweep, by registered family | `dev.packaging.build_scratch_reclaim.var_scratch_name` |
| `docs/_build/` | documentation build output | rebuilt in place | `dev.docs.build` |
| `.tmp-tui-visual-inventory/` | TUI surface renders for visual review | `just clean-apply` (`.tmp-*`) | `dev.tui._artifacts` |
| OS temp | `mkdtemp` families | the central sweep, by registered prefix | `tempfile.mkdtemp` with a swept prefix |

A run directory's name carries date, label, pid and uuid, so two runs over one
tree never overwrite each other and every measurement stays attributable.

Each `.logs/` run directory holds `run.log` (flushed per line, so a hung lane
still leaves evidence), `run.json` (machine-readable metadata written
atomically at the end), and `artifacts/`, `cache/` and `scratch/` beneath it.

## The commands and what they write

### Measurement and audit

| Command | Module | Output |
|---|---|---|
| `just audit-code` | `dev.audit.advisory` | `.logs/audit-runs/…-audit-code/` — `summary.json`, `summary.md`, one raw payload per dimension |
| `just audit-types` | `dev.quality.types --full` | `.logs/audit-runs/…-audit-types/` |
| `just audit-complexity` | `dev.audit.complexity` | `.logs/audit-runs/…-audit-complexity/` |
| `just audit-dead-weight` | `dev.audit.dead_weight` | `.logs/test-runs/…-audit-dead-weight/artifacts/dead-weight-signal.json` |
| `just audit-code-security` | `dev.audit.security` | stdout only |
| `just report-code-health[-monthly]` | `dev.audit.report` | `.logs/audit-runs/…/` — `report.json`, `report.md` |
| `just report-product-reachability` | `dev.audit.unreachable_code` | `.logs/audit-runs/…-report-product-reachability/` |
| `just report-product-write-paths` | `dev.audit.write_path_coverage` | `.logs/audit-runs/…-report-product-write-paths/` |
| `just report-terminology-coverage` | `dev.docs.terminology.coverage` | `.logs/audit-runs/…-terminology-coverage/coverage-report.json` |
| `just report-registry-conformance` / `-closure` / `-aeip` | `dev.registry.conformance`, `dev.registry.aeip` | stdout only; read-only observations |
| `just docs-terminology-report` | `dev.docs.terminology_handbook audit` | stdout only |

The wrapped commands run under `dev.test_runs.command --family … --label …`,
which is what mints the run directory and captures the child's streams into it.
The runner owns the tool invocation *and* its parsing, so a recipe and the
health report's matching dimension cannot drift apart.

### Tests

Every `test-*` recipe runs pytest under `dev.test_runs.logging`, which mints
`.logs/test-runs/<date>/<run-id>/` before any production import can bind
logging, and points `CADRUMO_LOG_DIR` and `CADRUMO_TEST_RUN_ROOT` inside it.
Lane orchestration (`dev.test_runs.lanes`) writes to `.logs/lane-runs/` instead.
The path is printed at the start and the end of every run — read it before the
next clean, because the next clean reclaims it.

### Registry migration

`just report-registry-edition-migration` and `just registry-edition-migrate`
take an operator-supplied `WORK_DIR` and keep their staging tree there; the run
report goes to `.logs/audit-runs/…-report-registry-edition-migration/`. The
work directory is refused if it overlaps the registry source it is migrating.

### Documentation and rendering

`just docs-build`, `docs-page` and `docs-serve` write under `docs/_build/`.
`just tui-review render` writes PNG/SVG renders of every TUI surface into
`.tmp-tui-visual-inventory/`. Both are disposable local output; neither uploads
anything.

### Reclaiming

`just clean` reports what would be removed. `just clean-apply` removes it —
destructively, irreversibly, and including locations outside this worktree (OS
temp, other sessions' scratch, test-run evidence). Both always exit 0, so the
exit status proves nothing: read the report.

## Adding a command that measures something

1. Allocate the destination with
   `dev.test_runs.paths.allocate_run_directory(REPO_ROOT, family=…, label=…)`,
   or run the command under `dev.test_runs.command`, which does it for you.
2. Print the path you wrote. A measurement nobody can find is not evidence.
3. Do not add a `.gitignore` entry for a path under `dev/`. Needing one is the
   signal that the destination is wrong.
