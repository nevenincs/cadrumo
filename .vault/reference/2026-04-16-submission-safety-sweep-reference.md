---
tags:
  - "#reference"
  - "#submission-safety-sweep"
date: "2026-04-16"
modified: '2026-04-16'
related:
  - "[[2026-04-16-submission-safety-sweep-research]]"
  - "[[2026-04-16-live-write-static-audit-reference]]"
  - "[[2026-04-16-live-write-static-audit]]"
  - "[[2026-04-12-submission-engine-adr]]"
---

# submission-safety-sweep reference brief

Scope: production hardening for issues `#142` through `#146`, limited to the current submission engine, amendment CLI, workflow submission contract, config/env docs, and the stubbed submission CLI helper.

## High-signal read

- The AEAT write leaf remains `Modelo130Submitter.submit`, but the missing charter gates are all above it in the engine/CLI/workflow contract.
- The safest contract change is to make `dry_run` required keyword-only at the submission and workflow boundaries while removing the legacy `override_confirmation` boolean from those APIs.
- The missing confirmation and audit surfaces belong inside `aeat.adapters.outbound.aeat.export` as private modules, invoked only from the live branch of the engine.
- The current CLI submission helper is still stub-only, so any live command that depends on it must fail closed rather than report success.

## Primary code surfaces

### Engine and package root

- `src/aeat/adapters/outbound/aeat/export/_engine.py`
- `src/aeat/adapters/outbound/aeat/export/_errors.py`
- `src/aeat/adapters/outbound/aeat/export/_models.py`
- `src/aeat/adapters/outbound/aeat/export/__init__.py`

### New internal modules

- `src/aeat/adapters/outbound/aeat/export/_confirm.py`
- `src/aeat/adapters/outbound/aeat/export/_audit.py`

### CLI surfaces

- `src/aeat/entrypoints/cli/submission/_helpers.py`
- `src/aeat/entrypoints/cli/submission/submit.py`
- `src/aeat/entrypoints/cli/submission/test_cli.py`
- `src/aeat/entrypoints/cli/filing/__init__.py`
- `src/aeat/entrypoints/cli/filing/test_filing_cli.py`

### Workflow surfaces

- `src/aeat/application/workflow/_protocols.py`
- `src/aeat/application/workflow/_engine.py`
- `src/aeat/application/workflow/_adapters.py`
- `src/aeat/application/workflow/test_engine.py`
- `src/aeat/entrypoints/cli/workflow/_helpers.py`
- `src/aeat/entrypoints/cli/workflow/run.py`
- `src/aeat/entrypoints/cli/workflow/next.py`
- `src/aeat/entrypoints/cli/workflow/test_cli.py`

### Config and environment contract

- `src/aeat/config.py`
- `env/.env.example`
- `tests/test_config.py`

## Required contract changes

### R2: explicit `dry_run=`

- Make `SubmissionEngine.submit_draft` require `dry_run` as a keyword-only argument with no default.
- Make `SubmissionEngine.submit_amendment` require `dry_run` as a keyword-only argument with no default.
- Mirror that signature in `SubmissionEngineProtocol`, `SubmissionEngineAdapter`, and the workflow engine call chain.
- Update every internal call site and test to spell out `dry_run=True` or `dry_run=False`.

### R3 and R5: live-submit env gate plus pytest refusal

- Add `Settings.aeat_live_submit_enabled` mapped to `AEAT_LIVE_SUBMIT_ENABLED`.
- Remove the old `aeat_submission_require_human_confirmation` setting and env example entry, because it models the wrong invariant and is not otherwise load-bearing on this branch.
- In the live branch of `SubmissionEngine._submit_with_transport`, refuse when:
  - `settings.aeat_live_submit_enabled` is false
  - `PYTEST_CURRENT_TEST` is present
- Use typed submission-domain errors for each refusal path.

### R4: dedicated confirmation hook

- Add a private confirmation helper in `aeat.adapters.outbound.aeat.export._confirm`.
- The helper should render:
  - modelo
  - period
  - taxpayer NIF
  - submission URL
  - filing checksum
- The helper should require an exact phrase, not `y/n`.
- The helper should remain private to `aeat.adapters.outbound.aeat.export`; do not re-export it from `aeat.adapters.outbound.aeat.export.__init__`.

### R6: append-only audit log

- Add a private audit helper in `aeat.adapters.outbound.aeat.export._audit`.
- Persist live-write records to `.aeat/live-submit-audit.log` as append-only structured JSON lines.
- Record:
  - UTC timestamp
  - modelo, period, taxpayer NIF
  - draft checksum
  - submission URL
  - submission status / justificante CSV when available
  - exact confirmation phrase entered
  - env-var state snapshot
  - process PID and argv
- Apply best-effort read-only file permissions after each append.

## CLI resolution for issue `#146`

- `aeat submission submit` cannot truthfully report a live success while `build_engine()` still uses `_NullSession`.
- The coherent fix on this branch is:
  - keep dry-run and read-only helper paths intact
  - make the live CLI path fail closed with a clear refusal explaining that the production transport is not wired
  - still rely on the engine-level charter gates for any future real transport caller
- The same fail-closed behavior should apply to amendment live CLI when it depends on the same stub engine factory.

## Expected test fallout

- Submission tests that currently rely on omitted `dry_run` defaults must be updated to pass `dry_run=True` explicitly.
- Workflow tests must update their fake protocol signatures and expected call tuples once `override_confirmation` disappears and `dry_run` becomes required.
- CLI tests must stop expecting a stub-backed `LIVE submission OK` path; they should assert refusal instead.
- Config-alignment tests will need the new env var added and the legacy one removed.
