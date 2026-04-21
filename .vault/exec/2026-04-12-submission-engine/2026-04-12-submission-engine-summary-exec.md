---
tags:
  - "#exec"
  - "#submission-engine"
date: 2026-04-12
title: submission engine — execution summary
related:
  - "[[2026-04-12-submission-engine-research]]"
  - "[[2026-04-12-submission-engine-adr]]"
  - "[[2026-04-12-submission-engine-plan]]"
  - "[[2026-04-12-submission-engine-phase1-schema-exec]]"
  - "[[2026-04-12-submission-engine-phase2-preflight-engine-exec]]"
  - "[[2026-04-12-submission-engine-phase3-modelo130-exec]]"
  - "[[2026-04-12-submission-engine-phase4-cli-exec]]"
  - "[[2026-04-12-submission-engine-phase5-verification-exec]]"
issue: wgergely/aeat#42
---

# execution summary: filing submission engine

## summary

Implemented `aeat.submission` per the ADR and plan. The subpackage
exposes `SubmissionEngine`, `Submitter` ABC, `Modelo130Submitter`,
`Preflight`, strict+frozen pydantic v2 records
(`SubmissionStatus`, `SubmissionAttempt`, `SubmittedFiling`), the
`SubmissionError` hierarchy, and Protocol stubs for every in-flight
sibling (#6 / #7 / #8 / #23 / #38 / #39 / #44). A narrow
`BrowserSessionLike` Protocol enables unit tests to pass deterministic
Protocol implementations without spinning up Playwright — fully
respecting the "no mocks" rule. The `aeat submission` Typer sub-app
wires five subcommands (`preflight`, `dry-run`, `submit`, `show`,
`list`); `submit` requires `--i-understand-this-is-real`. Four new
Settings fields (`AEAT_SUBMISSIONS_DIR`,
`AEAT_SUBMISSION_DRY_RUN_DEFAULT`,
`AEAT_SUBMISSION_REQUIRE_HUMAN_CONFIRMATION`,
`AEAT_SUBMISSION_BROWSER_TRACE_DIR`) are documented in
`env/.env.example` and the alignment test passes.

## artefacts produced

- `src/aeat/submission/__init__.py`
- `src/aeat/submission/_errors.py`
- `src/aeat/submission/_protocols.py`
- `src/aeat/submission/_models.py`
- `src/aeat/submission/_preflight.py`
- `src/aeat/submission/_engine.py`
- `src/aeat/submission/_submitters/__init__.py`
- `src/aeat/submission/_submitters/_contract.py`
- `src/aeat/submission/_submitters/modelo130.py`
- `src/aeat/submission/_submitters/test_modelo130.py`
- `src/aeat/submission/test_models.py`
- `src/aeat/submission/test_errors.py`
- `src/aeat/submission/test_preflight.py`
- `src/aeat/submission/test_engine.py`
- `src/aeat/submission/test_live_submission.py`
- `src/aeat/cli/submission/__init__.py`
- `src/aeat/cli/submission/_helpers.py`
- `src/aeat/cli/submission/preflight.py`
- `src/aeat/cli/submission/dry_run.py`
- `src/aeat/cli/submission/submit.py`
- `src/aeat/cli/submission/show.py`
- `src/aeat/cli/submission/list.py`
- `src/aeat/cli/submission/test_cli.py`
- `src/aeat/config.py` (modified: four new Settings fields)
- `env/.env.example` (modified: four new env vars)
- `src/aeat/cli/__init__.py` (modified: registered submission sub-app)

## verification

All verification gates listed in
`[[2026-04-12-submission-engine-phase5-verification-exec]]` passed on the
first clean run.

## follow-ups / rebase swaps

- Rebase-swap Protocol stubs in `_protocols.py` as #6 / #7 / #8 / #23
  / #39 / #44 land on ``main``.
- Hook `_engine.py`'s `browser_session_factory` to the real
  `aeat.browser.BrowserSession` factory in the CLI once the live
  submission flow is desired — the current CLI uses a `_NullSession`
  deterministic stub because v1 ships dry-run-only over in-process
  stubs.
- Parse the AEAT acknowledgement page into a `Justificante` inside
  `Modelo130Submitter.submit` once #44 merges.
