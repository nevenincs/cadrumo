---
name: workflow-engine-phase1-summary
description: Phase-1 summary for the composite workflow engine — ten-stage orchestrator, bailout matrix, CLI surface, persistence, and full local gates green.
tags:
  - "#exec"
  - "#workflow-engine"
date: 2026-04-12
modified: '2026-04-12'
related:
  - "[[2026-04-12-workflow-engine-plan]]"
  - "[[2026-04-12-workflow-engine-adr]]"
  - "[[2026-04-12-workflow-engine-research]]"
  - "[[2026-04-12-workflow-engine-phase1-step1-exec]]"
---

# workflow-engine phase-1 summary

## delivered

- `aeat.application.workflow` public API: `WorkflowEngine`, `run_next`,
  `run_for_period`, `WorkflowResult`, `WorkflowStep`,
  `WorkflowStage`, `WorkflowAbortReason`, error hierarchy, persistence
  helpers, eight `typing.Protocol` handles, adapters, and
  `default_engine(...)` factory.
- `aeat workflow {next,run,show,list}` typer sub-app mounted through
  `aeat.entrypoints.cli.__init__` via `app.add_typer`. Live-submit double-gate
  (`--no-dry-run --i-understand-this-is-real`) matches the
  submission engine's contract verbatim.
- Three additive settings — `AEAT_WORKFLOW_RUNS_DIR`,
  `AEAT_WORKFLOW_SYNC_FIRST_DEFAULT`,
  `AEAT_WORKFLOW_DRAFT_INPUTS_PATH` — landed in `aeat.core.config.Settings`
  and `env/.env.example`; `tests/test_config.py` alignment green.
- Unit test suite covers every `WorkflowAbortReason`, the happy path,
  the dry-run default, the stable `run_id` hash, the JSON round-trip,
  and the CLI surface. All tests use hand-rolled
  Protocol-conforming doubles.
- One `@pytest.mark.live` smoke test gated via
  `aeat.entrypoints.cli._live.requires_live_enabled()`; skipped by default per
  the project's `AEAT_LIVE_TESTS_ENABLED` contract.

## gates

- `just lint` — pass
- `just typecheck` — pass (ty, 0 diagnostics)
- `just test` — 444 passed, 1 skipped (live), 16 deselected
- `just hooks` — pass (prek, all hooks green on full tree)

## out of scope (per ADR)

- Live AEAT submission; live path is documented but requires the
  double gate on every call.
- Persistence via the `aeat.adapters.persistence.storage` subpackage (#10); files-only in
  v1.
- Rebasing onto the in-flight `#8 cert`, `#43 status`, `#46 inbox`
  branches — the Protocol slots remain `None`-by-default and rebase
  is a mechanical adapter wiring.
