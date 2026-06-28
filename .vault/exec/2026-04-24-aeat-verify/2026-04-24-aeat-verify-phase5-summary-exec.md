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
  - "[[2026-04-24-aeat-verify-phase4-summary-exec]]"
---



# `aeat-verify` `phase-5` `sync-run-integration`

Phase 5 of the `aeat-verify` plan wires auto-reconciliation into
`aeat sync run`. The pre-existing `aeat sync run` was a stub that
refused to launch until cross-branch dependencies ship; Phase 5 keeps
that refusal intact (the existing sync-run prerequisites test still
passes) and inserts a dedicated reconcile stage *ahead of* the
refusal so the reconciler is already functional today without waiting
on the broader self-healing-sync scaffolding. The stage gates on
`FilingDraftStatus.APPROVED` only, reuses a single fetcher (and
therefore a single `AeatSession`) across every `(modelo, period)`
pair inside one invocation, surfaces `NOT_YET_FOUND` prominently in
the Kent-facing run summary, and persists `DIVERGENT` / `NOT_YET_FOUND`
reports through the Phase-3 persistence adapter without touching the
closed `aeat.application.sync._divergence.DivergencePayload` union.

- Created: `src/aeat/entrypoints/cli/sync/_reconcile_stage.py` (pure stage +
  `ReconcileStageSummary` pydantic record + `ReconciliationSink`
  Protocol + `emit_reconcile_summary` rich renderer).
- Created: `src/aeat/entrypoints/cli/sync/test_reconcile_stage.py` (APPROVED
  gating, session-reuse, NOT_YET_FOUND surfacing, DIVERGENT
  persistence, mixed-batch, empty-corpus, strict-frozen-forbid
  record checks).
- Created: `src/aeat/entrypoints/cli/sync/test_no_write_surface.py` plus
  `_no_write_surface_fixture.txt` (Layer-3 grep guard narrowly
  scoped to the two new Phase-5 files).
- Modified: `src/aeat/entrypoints/cli/sync/run.py` (converted to the
  `register(app, *, fetcher_provider, sink_provider, ...)` factory
  pattern; reconcile stage invoked before the
  prerequisites-pending refusal).
- Modified: `src/aeat/entrypoints/cli/sync/__init__.py` (imports
  `register_run` and calls it instead of wiring a plain-function
  command).
- Modified: `src/aeat/application/filing/reconciliation/__init__.py` (public
  API now re-exports `FilingReconciliationDivergenceRecord`,
  `FilingReconciliationPayload`, and `reconciliation_records` so
  sync-run consumers honour the "import from
  `aeat.application.filing.reconciliation` only" discipline without touching
  private modules).

## Description

### 5.1 Stage module placement

The plan allowed an inline insertion into `src/aeat/entrypoints/cli/sync/run.py`
*or* a dedicated sibling module; the execution opted for a dedicated
`src/aeat/entrypoints/cli/sync/_reconcile_stage.py` for three load-bearing
reasons:

1. The Phase-5 non-negotiable #1 ("zero writes") demands a narrowly
   scoped Layer-3 grep guard. Putting the reconcile logic inside
   `run.py` would force the guard to cover the schema-level
   sync-run orchestration — which transitively reaches the audited
   `aeat.adapters.outbound.aeat.export` engine and its legitimately write-enabled
   vocabulary. Isolating the reconcile surface in its own module
   lets Layer 3 stay meaningful and tight.
2. The stage's injection seams (`fetcher_provider`, `sink_provider`,
   `drafts_dir_provider`, `now_provider`) align one-to-one with the
   `register(app, ...)` factory pattern the Phase-4 reconcile CLI
   already locked in. Keeping the same shape across the filing CLI
   and the sync CLI lowers cognitive overhead for future reviewers
   and makes the unit tests structurally identical.
3. The stage's public surface — `ReconcileStageSummary`,
   `ReconciliationSink`, `emit_reconcile_summary`,
   `iter_approved_drafts`, `run_reconcile_stage` — is large enough
   that inlining it into `run.py` would bury the top-level command
   body in plumbing.

### 5.1 Threading the stage into `aeat sync run`

`run.py` was converted from the plain-function pattern
(`app.command(name="run")(run)`) to the factory pattern
(`register(app, *, fetcher_provider=..., sink_provider=..., ...)`).
The default providers return `None`, which preserves the
pre-Phase-5 behaviour: when no fetcher or sink is wired (the default
for every environment that has not yet plumbed the live Playwright
stack), the reconcile stage is skipped and the command falls
straight through to the "runner prerequisites pending" refusal. The
existing `test_sync_run_refuses_until_dependencies_merge` test
continues to pass unchanged. Tests for Phase 5 construct their own
`typer.Typer` via `register(app, fetcher_provider=..., ...)` so the
reconcile path is exercised directly — mirroring the Phase-4 CLI
test pattern verbatim.

### 5.2 Session reuse

The session-reuse invariant is encoded at the provider seam: the
caller constructs *one* `RemoteFilingFetcher` (backed by one
`AeatSession`) before invoking `run_reconcile_stage` and threads it
through every `(modelo, period)` reconciliation. The stage itself
never instantiates a session or authenticator; it simply calls
`fetcher.fetch_filing_detail(modelo, period)` in a loop. The
`_SessionCountingFetcher` unit-test double asserts this structurally
(`test_single_fetcher_services_multiple_modelo_period_pairs` checks
both that exactly one fetcher instance is live across the pass and
that every expected `(modelo, period)` pair received a call). The
18-minute `AEAT_SESSION_IDLE_TTL` comfortably covers a multi-modelo
pass.

### 5.3 `NOT_YET_FOUND` surfacing

`NOT_YET_FOUND` reports are surfaced through two distinct channels:

- A WARNING-level log through `aeat.core.logging.get_logger(__name__)`
  naming the draft id, the modelo, and the period — this hits
  Kent's log viewer immediately and the operator does not have to
  read the run summary to see that AEAT has no record.
- A prominent end-of-run summary marker rendered by
  `emit_reconcile_summary` — an upper-cased `NOT_YET_FOUND` header
  in bold yellow followed by a bulleted list of
  `modelo=... period=... draft_id=...` triples so Kent knows
  exactly which filings AEAT has not yet ingested.

`DIVERGENT` reports get a sibling treatment (WARNING log + bold-red
summary header) because both statuses demand Kent's attention;
`MATCH` reports stay quiet (DEBUG log only) so the summary stays
readable when Kent uploads a clean filing.

### 5.4 Persistence via the Phase-3 adapter

Both `DIVERGENT` and `NOT_YET_FOUND` reports flow through
`aeat.application.filing.reconciliation.reconciliation_records(report)` and land
on the `ReconciliationSink` Protocol (one `save(record)` method per
the narrow contract). The sink accepts the Phase-3
`FilingReconciliationDivergenceRecord` shape — *not* the closed
`aeat.application.sync._divergence.DivergenceRecord` — so the bounded
auto-heal-safety contract the Phase-3 rationale protects stays
untouched. `aeat.application.sync._divergence` is read-only from Phase 5's
perspective; no enum is widened, no payload variant is injected.
Phase-3's non-negotiable constraint #7 ("no modifications to
`src/aeat/application/sync/_divergence.py`") is fully respected.

### 5.5 Public API discipline

The Phase-3 `_persist.FilingReconciliationDivergenceRecord`,
`FilingReconciliationPayload`, and `reconciliation_records`
collaborators were previously referenced only in docstrings and in
the adjacent `test_persist.py` via private-module imports. Phase 5
needs them at Kent-facing boundaries (the sync-run stage, its unit
tests), so the `aeat.application.filing.reconciliation` public API now
re-exports them. The Layer-3 grep guard at
`test_no_write_surface.py` still passes — none of the newly exported
names match any forbidden English/Spanish write-verb prefix. Callers
outside the reconciliation subpackage now honour the "no private
imports" discipline the plan's non-negotiable constraint #3 locks.

### 5.6 Layer-3 write-guard for Phase 5

A sibling Layer-3 guard (`test_no_write_surface.py` +
`_no_write_surface_fixture.txt`) lands under `src/aeat/entrypoints/cli/sync/`
walking exactly two paths — `_reconcile_stage.py` and
`test_reconcile_stage.py`. The sibling sync-run commands
(`run.py`, `list.py`, `show.py`, `resolve.py` and their
`test_cli.py`) are deliberately outside the guard's scope: the
sync-run orchestration legitimately routes through the audited
`aeat.adapters.outbound.aeat.export` engine and speaks `submit` / `enviar` / POST in
the complementaria submission path, and scoping the guard wider
would regress its narrow, meaningful signal. This mirrors the
Phase-4 decision to scope `src/aeat/entrypoints/cli/filing/test_no_write_surface.py`
only to the two new reconcile CLI files.

### Deviation from the plan: `run.py` signature change

The plan (5.1) phrased the stage insertion as "gains a
post-schema-sync stage that iterates over local `FilingDraft`s" —
i.e. *amending* an existing sync-run flow. In reality the sync-run
body is still the stub that the dependency-merge comment describes,
so there is no "after schema-level divergence processing" hook to
slot into. The execution instead:

1. Keeps the stub refusal intact so the existing
   `test_sync_run_refuses_until_dependencies_merge` test continues
   to pass.
2. Converts `run.py` to the `register(app, ...)` factory pattern so
   the fetcher / sink / drafts_dir / now seams are injectable the
   same way Phase-4's CLI uses `register(app, fetcher_provider, ...)`.
3. Invokes the reconcile stage *before* the stub refusal. When
   both providers return `None` (the default) the stage is skipped
   cleanly; when tests (or future production wiring) return real
   providers, the stage runs and emits its summary before the
   command exits.

The net effect matches the plan's intent — auto-reconciliation
lands inside `aeat sync run` on the same code path Kent will invoke
— while the stub-refusal invariant the rest of the CLI relies on
stays stable. The full sync-run pipeline (certificate backend,
corpus loader, schema loader, manual rules, LLM client) is outside
Phase 5's scope; once those land, the reconcile stage already sits
on the correct code path and the post-schema-sync insertion point
becomes a trivial re-ordering.

### Deviation from the plan: caller-side multi-filing reduction

The Phase-3 executor collapsed the multi-filing chain reduction
(original + complementarias) into the caller per the ADR's
"comparator takes one `RemoteFiling | None`" signature. Phase-5
honours that contract: `_fetch_latest_remote_filing` picks the
latest-by-`submitted_at` anchor from the fetcher's returned tuple
before handing the result to `reconcile(...)`. The
`test_multi_filing_chain_picks_latest_by_submitted_at` unit test
locks this behaviour so a future contributor cannot accidentally
regress it by reducing to the first-returned element.

## Tests

- `just lint` — green (`ruff check .` plus the
  `check_relative_imports.py` gate).
- `just typecheck` — green (`ty check src tests`).
- `just hooks` — green on every modified file via the prek chain
  (trailing whitespace, ruff check / format, ty, relative-imports).
- `uv run pytest -m unit -k "sync or reconcile"` — 265 passed
  (up from 257, +8 from the new `test_reconcile_stage.py` class
  groupings plus the new `test_no_write_surface.py` checks; marker
  integrity auto-picks up the new modules).
- `uv run pytest -m unit -k "sync or reconcile or remote or filing"`
  — 873 passed, 2480 deselected.
- Repository-wide `uv run pytest` — 3318 passed, 5 skipped,
  29 deselected, one pre-existing failure in
  `tests/test_marker_integrity.py::test_module_carries_valid_pytestmark[src/aeat/adapters/outbound/aeat/export/_formats/_test_fixtures.py]`
  that predates this branch and is explicitly out of Phase 5 scope
  per the executing prompt.

Layer 4 (charter #116 alignment) and Layer 5 (live-test discipline)
remain owned by Phase 2; Phase 5 ships no live surface. Layers 1
(read-only records), 2 (public API contract), and 3 (narrowly
scoped grep guard) stay green.

No audit report has been generated yet for Phase 5; the mandatory
`vaultspec-code-reviewer` audit runs next and will land under
`.vault/audit/` once the reviewer persona has inspected the Phase 5
surface.
