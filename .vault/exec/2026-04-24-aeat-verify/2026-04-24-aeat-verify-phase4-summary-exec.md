---
tags:
  - '#exec'
  - '#aeat-verify'
date: '2026-04-24'
modified: '2026-04-24'
related:
  - "[[2026-04-24-aeat-verify-plan]]"
  - "[[2026-04-24-aeat-verify-adr]]"
  - "[[2026-04-24-aeat-verify-phase1-summary-exec]]"
  - "[[2026-04-24-aeat-verify-phase2-summary-exec]]"
  - "[[2026-04-24-aeat-verify-phase3-summary-exec]]"
---



# `aeat-verify` `phase-4` `cli-surface`

Phase 4 of the `aeat-verify` plan lands the `aeat filing reconcile`
subcommand as a sibling of `aeat filing import`. The command consumes
the Phase-3 `aeat.application.filing.reconciliation.reconcile` comparator and the
Phase-1 `aeat.remote.RemoteFilingFetcher` Protocol so the CLI surface
stays Phase-5-ready (sync-run integration reuses the same shape). The
write-guard posture the ADR locks is preserved end-to-end: no flag
declared in this module mutates AEAT state, and the narrow
source-scoped Layer-3 grep guard walks only the new files.

- Created: `src/aeat/entrypoints/cli/filing/_reconcile.py` (reconcile subcommand,
  pre-parse flag guard, strict-pydantic `ReconcileCliArgs`, draft
  resolvers, human + JSON rendering, exit-code mapping).
- Created: `src/aeat/entrypoints/cli/filing/test_reconcile.py` (43 unit cases
  covering every Phase-4 acceptance item).
- Created: `src/aeat/entrypoints/cli/filing/test_no_write_surface.py` (Layer-3
  grep guard narrowly scoped to the two new source files).
- Created: `src/aeat/entrypoints/cli/filing/_no_write_surface_fixture.txt`
  (plain-text sidecar mirroring the Phase-1 / Phase-3 fixture shape).
- Modified: `src/aeat/entrypoints/cli/filing/__init__.py` (import-and-register the
  reconcile subcommand; added the `reconcile` entry to the module
  docstring).

## Description

### 4.1 Subcommand registration

The subcommand registers via `_reconcile.register(app)` from the
`aeat filing` sub-app. The registration seam takes two factory
callables (`fetcher_provider` + `now_provider`) so the unit suite
wires a deterministic `_StaticFetcher` and a frozen clock without
touching module-level state. The Typer command declares the
`draft_id` positional argument plus `--modelo`, `--period`, `--last`,
`--json`, and `--dry-run` options. No forbidden flag
(`--write`, `--submit`, `--enviar`, `--presentar`, `--firmar`,
`--commit`, `--send`) is declared as a Typer option anywhere in the
module — declaring them would defeat the guard. Typer's own
unknown-flag parser catches them at exit-code 2 with the canonical
"No such option" error. The module-level `reject_forbidden_flags`
adds defence-in-depth against `--flag=value`-shaped inputs that
might slip past a future option declaration.

### 4.2 JSON output

`--json` renders `report.model_dump(mode="json")` to stdout with
deterministic key ordering (`sort_keys=True`) and `ensure_ascii=False`
so the trilingual narrative renders cleanly on a UTF-8 terminal.
Machine consumers read the `status` field; the CLI exits `0`
regardless of the terminal-triad member when `--json` is active. The
`TestJsonOutput.test_json_divergent_still_exits_zero` case locks this
invariant.

### 4.3 Dry-run alias

`--dry-run` is a documented no-op alias. The help text explicitly
tells Kent that the command is read-only by construction and the flag
exists only for symmetry with the sibling filing commands that need
it.

### 4.4 Unit tests

`test_reconcile.py` covers:

- Happy-path `MATCH` with green narrative + exit 0.
- `DIVERGENT` with casilla-level delta in the table + exit 1.
- `NOT_YET_FOUND` with prominent warning narrative + exit 2.
- Parser refusal of every entry in `_FORBIDDEN_FLAGS`
  (`--write`, `--submit`, `--enviar`, `--presentar`, `--firmar`,
  `--commit`, `--send`) with exit-code 2 and a non-empty stderr
  message. Typer's unknown-flag surface handles the refusal; the
  module-level `reject_forbidden_flags` covers the
  `--flag=value` shape independently.
- `--json` round-trip: `json.loads(result.stdout)` yields a mapping
  carrying every documented `ReconciliationReport` field
  (`status`, `casilla_deltas`, `remote_ref`, `draft_ref`,
  `reconciled_at`, `narrative`).
- `--last --modelo 303 --period 2025-1T` picks the most recent
  approved draft (sorted by `approved_at`, falling back to
  `updated_at`).
- Unknown draft id emits a helpful `typer.BadParameter` (exit != 0,
  no traceback in output).
- `--last` without `--modelo` / `--period` is refused; passing both
  a draft id and `--last` is refused.
- `--dry-run` behaves identically to no flag (read-only alias).

All tests are `@pytest.mark.unit` + `@pytest.mark.domain_submission`;
the marker integrity walker registers the new modules automatically.

### 4.5 Write-guard Layer 3 reuse

`test_no_write_surface.py` walks exactly two paths
(`_reconcile.py` + `test_reconcile.py`) and applies the same five
checks the Phase-1 and Phase-3 grep guards run: Playwright-mutating
fragments, call-context write verbs, mutating HTTP verbs, the
composed `mode="write"` literal, and `^<verb-prefix>` against the
reconcile module's `__all__`. The fixture-sidecar pattern is preserved:
the fixture is a `.txt` file, never importable Python, and composes
the forbidden literal at runtime so no guarded source materialises
the forbidden string. The guard is deliberately **not** scoped to the
whole `src/aeat/entrypoints/cli/filing/` tree because sibling commands
(`submit_complementaria_cmd`, the complementaria build/submit pair)
legitimately speak `submit` / `enviar` / `send` via the audited
submission engine in `aeat.adapters.outbound.aeat.export`.

### Deviation from the plan: dedicated source module

The plan text (4.1) suggested adding the subcommand "as a sibling of
the existing `import_`" inside `src/aeat/entrypoints/cli/filing/__init__.py`.
The execution instead puts the reconcile command in a dedicated
sibling `src/aeat/entrypoints/cli/filing/_reconcile.py` and wires it via a
`register(app, ...)` call from `__init__.py`. Three concrete reasons:

1. The Phase-4 non-negotiable #1 (zero writes) demands a source-level
   grep guard scoped tightly. Putting reconcile inside
   `__init__.py` would force the guard to cover
   `submit_complementaria_cmd` and the complementaria submission
   plumbing, which are by design write-enabled surfaces routed
   through the audited `aeat.adapters.outbound.aeat.export` engine. Keeping the two
   surfaces in separate files lets Layer 3 stay narrow and
   meaningful.
2. The `register(app, *, fetcher_provider, now_provider)` factory
   pattern is the cleanest injection seam for the unit tests —
   wiring a Protocol-conforming `_StaticFetcher` plus a frozen clock
   to the live command without patching module state. The
   `__init__.py` sibling commands predate this project invariant
   and use `asyncio.run(engine.submit_amendment(...))`-shaped
   direct wiring.
3. The prompt explicitly allows the "or its appropriate sibling
   file — match whatever pattern `aeat filing import` currently
   uses" phrasing; the Layer-3 grep guard is the pattern the
   reconcile surface must match.

## Tests

- `just lint` — green (`ruff check .` plus the
  `check_relative_imports.py` gate).
- `just typecheck` — green (`ty check src tests`).
- `just hooks` — green on every modified file via the prek chain
  (trailing whitespace, ruff check / format, ty, relative-imports).
- `uv run pytest src/aeat/entrypoints/cli/filing/ -m unit` — 52 passed
  (43 new from Phase 4, 9 pre-existing from `test_filing_cli.py`).
- `uv run pytest -m unit -k "filing or reconcile or remote"` —
  823 passed, 2497 deselected; includes every marker-integrity walker
  over the three new test modules.
- Repository-wide `uv run pytest` — 3285 passed, 5 skipped,
  29 deselected. One pre-existing failure in
  `tests/test_marker_integrity.py::test_module_carries_valid_pytestmark[src/aeat/adapters/outbound/aeat/export/_formats/_test_fixtures.py]`
  that predates this branch and is explicitly out of Phase 4 scope
  per the executing prompt.
- Live CLI smoke: `uv run aeat filing reconcile --write` exits `2`
  with "No such option: --write" (Typer's standard unknown-flag
  refusal); `uv run aeat filing reconcile --help` lists the five
  documented options and no forbidden flag.

Phase 5 (sync-run integration) remains pending. No audit report has
been generated yet for Phase 4; the mandatory `vaultspec-code-reviewer`
audit runs next and will land under `.vault/audit/` once the reviewer
persona has inspected the Phase 4 surface.
