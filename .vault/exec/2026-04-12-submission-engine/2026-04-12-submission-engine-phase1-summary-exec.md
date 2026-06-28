---
tags:
  - "#exec"
  - "#submission-engine"
date: 2026-04-12
modified: '2026-04-12'
title: Filing Submission Engine — Phase Summary
related:
  - "[[2026-04-12-submission-engine-research]]"
  - "[[2026-04-12-submission-engine-adr]]"
  - "[[2026-04-12-submission-engine-plan]]"
issue: wgergely/aeat#42
---

# exec summary: filing submission engine

## scope delivered

- `src/aeat/adapters/outbound/aeat/export/` subpackage: strict pydantic v2 schema
  (`SubmissionStatus`, `SubmissionAttempt`, `SubmittedFiling`,
  `make_submission_id`), error hierarchy (`SubmissionError` +
  `SubmissionPreflightError` + `SubmissionFormFillError` +
  `SubmissionRejectionError`, all rooted at `aeat.core.errors.AeatError`),
  `_protocols.py` stubs for every in-flight sibling (#6/#7/#8/#23/
  #38/#39/#44), four-gate `Preflight` validator, `SubmissionEngine`
  orchestrator with dry-run default and double-gate live submission,
  `Submitter` ABC, and the `Modelo130Submitter` PoC.
- `src/aeat/entrypoints/cli/submission/` Typer sub-app wired as
  `aeat submission {preflight,dry-run,submit,show,list}`. The
  `submit` command requires the explicit
  `--i-understand-this-is-real` flag; without it the command exits 2.
- Four new Settings fields (`aeat_submissions_dir`,
  `aeat_submission_dry_run_default`,
  `aeat_submission_require_human_confirmation`,
  `aeat_submission_browser_trace_dir`) plus aligned
  `env/.env.example` entries. `tests/test_config.py` stays green.
- Colocated unit tests (`@pytest.mark.unit`) covering: pydantic
  invariants + stable hash, four preflight gates, Modelo 130 dry-run
  / submit / unknown casilla, engine default-dry-run safety, engine
  double-gate live refusal, persistence round-trip, list filtering,
  Typer sub-app (preflight / dry-run / submit refusal / show / list).
- Opt-in live rehearsal test
  `src/aeat/adapters/outbound/aeat/export/test_live_submission.py` marked
  `@pytest.mark.live` and gated on `AEAT_LIVE_TESTS=1`. Always runs
  dry-run; never submits.

## rules respected

- All code under `src/aeat/`.
- Public API discipline: every cross-module import of submission
  types goes through the `aeat.adapters.outbound.aeat.export` package root.
- Pydantic v2 strict+frozen for every boundary-crossing record; no
  dataclasses for public types; no bare `dict[str, Any]` on public
  signatures or persisted artefacts.
- Errors inherit from `aeat.core.errors.AeatError`; logging via
  `aeat.core.logging.get_logger(__name__)` only.
- Tests are pytest-only with exactly one of `@pytest.mark.unit` /
  `@pytest.mark.live`. The unit tests use real Protocol-conforming
  hand-written doubles, never mocks/patches/fakes.
- The dry-run default and the double-gate rule are enforced at the
  API level (`SubmissionEngine.submit_draft`) AND surfaced to the
  CLI (`--i-understand-this-is-real`).
- No hard imports from `aeat.application.filing`, `aeat.domain.deadlines`, `aeat.domain.modelos`,
  `aeat.domain.portals`, `aeat.adapters.outbound.aeat.auth.certificate`, `aeat.domain.casillas`, or
  `aeat.domain.justificante` — every cross-package dependency is a narrow
  Protocol stub in `aeat.adapters.outbound.aeat.export._protocols` ready for rebase-swap.

## verification

- `uv run ruff check .` → clean.
- `uv run ty check src tests` → clean (0 diagnostics).
- `uv run pytest -q` → 362 passed, 1 skipped, 10 deselected
  (`@pytest.mark.live` suites).
- `uv run prek run --all-files` → all hooks pass (whitespace,
  EOF, YAML, TOML, merge conflict, private-key, ruff, ruff format,
  ty).

## out-of-scope deliberately not done

- Submitters for modelos other than 130 (each is a follow-up).
- Justificante PDF parsing (#44 owns this; stub only).
- SQLite / #10 storage integration for persisted filings.
- Retry loops / auto-recovery from rejections.
- Any modification to `pyproject.toml [tool.pytest]` or
  `tests/conftest.py` (that is feature-15 territory).
