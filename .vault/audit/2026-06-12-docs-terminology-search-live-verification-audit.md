---
tags:
  - '#audit'
  - '#docs-terminology-search'
date: '2026-06-12'
modified: '2026-06-12'
related:
  - '[[2026-06-10-docs-terminology-search-plan]]'
  - '[[2026-06-12-docs-terminology-search-close-honesty-audit]]'
  - '[[2026-06-12-docs-terminology-search-rung2-adjudication-audit]]'
---

# `docs-terminology-search` audit: `live verification sweep`

## Scope

Current-state verification for the docs terminology search feature after the
hand-tested RAG sweep requirement was raised. This audit covers the
Terminology Handbook package, the dev docs terminology compiler and tests, the
resident vaultspec-rag service, and the bounded live RAG sweep over the
acceptance concepts `prorrata`, `casilla`, `modelo-303`, and
`recargo-equivalencia`.

## Live Service State

Before the live checks, the resident RAG service reported ready but had
watcher-driven index jobs running over this worktree and the vaultspec-rag
worktrees. The watcher roots were stopped through `vaultspec-rag server watcher
stop`. The final watcher state reported no watched roots and no running jobs.
The final service status used for the live checks was ready on port `8766`,
CUDA enabled, and models loaded.

## Verification Commands

- `uv run vaultspec-core vault plan status .vault/plan/2026-06-10-docs-terminology-search-plan.md`
  - `32 of 32 (100.0%)`.
- `uv run vaultspec-core vault plan check .vault/plan/2026-06-10-docs-terminology-search-plan.md`
  - Passed.
- `uv run pytest src/aeat/terminology dev/docs/terminology -q`
  - `190 passed, 1 deselected`.
- `uv run --no-sync vaultspec-rag search "regla de prorrata" --type code --port 8766 --max-results 8 --timeout 120 --json`
  - Passed through the service and returned the expected prorrata legal
    grounding hits, including LIVA Article 102 and the IVA legal catalogue row.
- `uv run --no-sync vaultspec-rag search "regla de prorrata" --type code --port 8766 --max-results 5 --timeout 120 --json`
  - Timed out client-side at 120 seconds after the watcher stop. Service logs
    showed the server-side search completed later, so this was recorded as
    cold-path latency evidence, not accepted as a green probe.
- `uv run --no-sync vaultspec-rag search "regla de prorrata" --type code --port 8766 --max-results 5 --timeout 600 --json`
  - Passed through the service after the timeout adjustment, returning the IVA
    legal catalogue row and extracted LIVA Article 102 surfaces as the top
    results.
- `uv run pytest dev/docs/terminology/tests/test_sweep.py::test_live_service_sweep_runs_at_least_one_term -q -m integration -rs`
  - `1 passed`.
- `uv run python -m dev.docs.terminology.sweep --concept prorrata --concept casilla --concept modelo-303 --concept recargo-equivalencia --no-reindex --timeout 120 --max-results 20`
  - Completed: `16 queries over 4 concept(s); 11 with targets, 5 empty (below floor)`.
- `uv run python -m aeat.terminology audit --ratchet-check`
  - Passed; curation ratchet clean at `75/75`.
- `uv run ruff check src/aeat/terminology dev/docs/terminology`
  - Passed.
- `uv run ruff format --check src/aeat/terminology dev/docs/terminology`
  - Passed after formatting three existing terminology files and one typed test edit.
- `uv run ty check dev/docs/terminology src/aeat/terminology`
  - Passed after tightening test helper annotations.
- `uv run pytest src/aeat/tests/test_wheel_bundles_corpus_and_registry.py src/aeat/core/tests/test_resources.py -q`
  - `22 passed`.
- `uv run python -m dev.docs.apidocs scaffold --check`
  - Passed; no API stub drift.
- `uv run pytest dev/docs/terminology -m "unit or integration" -q -rs`
  - `91 passed`.
- `uv run vaultspec-core vault check all -f docs-terminology-search --no-hints`
  - Feature-local vault checks are clean for annotations, links, features,
    references, schema, and rename integrity. The command still exits non-zero
    because two `ledger-amount-direction` exec filenames outside this
    workstream violate vault structure rules.
- `uv run --no-sync vaultspec-rag server status`
  - Service reported `running`, `Health ready`, `CUDA True`, `Models loaded
    True`, and port `8766` listening.
- `uv run --no-sync vaultspec-rag server watcher status`
  - No roots currently watched.
- `uv run --no-sync vaultspec-rag server jobs --json --limit 10`
  - No running jobs; latest watcher jobs are `done` or `cancelled`.

## Files Touched By This Verification Pass

- `src/aeat/terminology/_schema.py`
- `src/aeat/terminology/_seed_import.py`
- `src/aeat/terminology/tests/test_scaffold.py`
- `dev/docs/terminology/tests/test_casilla_projection.py`
- `dev/docs/terminology/tests/test_cli_projection.py`
- `dev/docs/terminology/tests/test_relevance_data.py`
- `dev/docs/terminology/tests/test_resolution.py`
- `dev/docs/terminology/tests/test_unified_record.py`
- `.vault/audit/2026-06-11-docs-terminology-search-audit.md`
- `.vault/audit/2026-06-12-docs-terminology-search-live-verification-audit.md`
- `.vault/index/docs-terminology-search.index.md`
- `.vault/plan/2026-06-10-docs-terminology-search-plan.md`

The worktree also already contains a same-package localization edit in
`src/aeat/terminology/cli.py`; it was observed and tested in this pass, but not
authored by this audit update.

## Findings

### LIVE-001 | VERIFIED | RAG service path is live and functional

The direct `regla de prorrata` service query returned high-scoring results from
the legal catalogue and the extracted LIVA normatives corpus. The live pytest
integration gate also passed without skip, proving the real
`ServiceRagSearchClient` path can search, resolve, wrangle, and produce at
least one target.

### LIVE-002 | VERIFIED | Bounded manual sweep completes under explicit timeout

The bounded four-concept live sweep completed with no retrieval failure. It
mapped 11 of 16 acceptance queries and recorded 5 honest below-floor empty
queries. The empty mappings are not silent failures: they are represented by
the sweep output as below-floor results.

### LIVE-003 | VERIFIED | Hardening gates are clean after type and format cleanup

The terminology package and dev docs terminology compiler now pass focused
pytest, ruff lint, ruff format, and `ty` checks. The type cleanup was limited
to test helper annotations so the checker sees concrete projection/resolution
record types instead of `object`.

### LIVE-004 | RESIDUAL | Full relevance quality is not perfect coverage

The committed relevance artifact is still intentionally honest about thin
coverage: the S30 held-out miss-rate audit records an 80.00% miss rate and the
current bounded live sweep still has 5 below-floor empties. The live path is
functional and the tests are green, but this audit does not claim every
possible terminology query maps to a target. A future relevance-refresh or
curation pass can improve coverage without changing the completed architecture.

## Closure Decision

The live RAG service path, bounded manual sweep, focused terminology tests,
format/lint/type checks, packaging resource checks, and docs scaffold check are
green for the current feature scope. The docs terminology search plan remains
structurally closed. Completion should be described as a hardened and
hand-tested compiled RAG terminology search surface with explicit residual
relevance-quality follow-up, not as full semantic coverage for every enrolled
query.
