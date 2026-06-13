---
tags:
  - "#plan"
  - "#submission-safety-sweep"
date: "2026-04-16"
modified: '2026-04-16'
related:
  - "[[2026-04-16-submission-safety-sweep-research]]"
  - "[[2026-04-16-submission-safety-sweep-reference]]"
  - "[[2026-04-16-submission-safety-sweep-adr]]"
  - "[[2026-04-16-live-write-static-audit]]"
---

# `submission-safety-sweep` `phase-1` plan

Implement the five-issue AEAT live-write safety sweep by moving the live-submit contract into `aeat.adapters.outbound.aeat.export`, tightening every live-capable signature to require explicit `dry_run=`, and failing closed on any CLI path that still depends on stubbed transport wiring.

## Proposed Changes

- Replace the old live-submit safety setting with a new `AEAT_LIVE_SUBMIT_ENABLED` config/env contract.
- Add private confirmation and audit helpers inside `aeat.adapters.outbound.aeat.export` and wire them into the engine live branch.
- Remove the legacy `override_confirmation` API contract from submission/workflow surfaces so the live/dry-run choice is carried only by explicit `dry_run=`.
- Refuse live mode under pytest and on stub-backed CLI paths.
- Update config/env docs and all affected tests so the new contract is explicit and verified.

## Tasks

- `phase-1 — engine safety contract`
  1. Update `src/aeat/config.py`, `env/.env.example`, and `tests/test_config.py` for the new live-submit env gate and remove the legacy misleading gate.
  1. Extend `src/aeat/adapters/outbound/aeat/export/_errors.py` with typed live-submit refusal errors and expose only the domain-safe public symbols through `src/aeat/adapters/outbound/aeat/export/__init__.py`.
  1. Add `src/aeat/adapters/outbound/aeat/export/_confirm.py` and `src/aeat/adapters/outbound/aeat/export/_audit.py` as private helpers for exact-phrase confirmation and append-only audit logging.
  1. Rework `src/aeat/adapters/outbound/aeat/export/_engine.py` so `submit_draft` and `submit_amendment` require explicit `dry_run=`, enforce env/pytest/confirmation/audit logic in the live branch, and preserve dry-run behavior.

- `phase-2 — caller alignment`
  1. Update submission CLI surfaces in `src/aeat/entrypoints/cli/submission/` so dry-run stays available, live mode fails closed when `_NullSession` is still the transport, and no stubbed path reports live success.
  1. Update amendment CLI live handling in `src/aeat/entrypoints/cli/filing/__init__.py` so it stops reusing `AEAT_LIVE_TESTS_ENABLED` and no longer performs a `typer.confirm` shortcut.
  1. Tighten workflow submission signatures across `src/aeat/application/workflow/_protocols.py`, `_engine.py`, `_adapters.py`, and the CLI workflow helpers so every live-capable call site spells out `dry_run=` explicitly.

- `phase-3 — verification and records`
  1. Update submission, filing, workflow, and config tests for the new signature and refusal behavior, with focused coverage for env-gate refusal, pytest refusal, fail-closed stubbed live CLI, and preserved dry-run success.
  1. Persist execution records under `.vault/exec/2026-04-16-submission-safety-sweep/` as the code changes land.
  1. Run targeted pytest slices first, then broader verification for the touched submission/workflow/CLI surfaces, and finish with a formal code-review audit artifact.

## Parallelization

The work is mostly serial because the core decision lives in `aeat.adapters.outbound.aeat.export._engine.py` and cascades into CLI/workflow signatures and tests. The only safe parallelism is review-only support: independent ADR/plan/code-review audits can run alongside local implementation, but code edits should stay in one thread to avoid contract drift across the same files.

## Verification

- Mission success requires all five issues to be closed by behavior, not by narrative:
  - live-capable APIs require explicit `dry_run=`
  - live submit is refused when `AEAT_LIVE_SUBMIT_ENABLED` is false
  - live submit is refused when `PYTEST_CURRENT_TEST` is present
  - the confirmation hook is exact-phrase and private to `aeat.adapters.outbound.aeat.export`
  - the live audit log is appended on successful live attempts
  - stub-backed CLI live mode no longer reports success
- Run targeted tests for:
  - `tests/test_config.py`
  - `src/aeat/adapters/outbound/aeat/export/test_engine.py`
  - `src/aeat/entrypoints/cli/submission/test_cli.py`
  - `src/aeat/entrypoints/cli/filing/test_filing_cli.py`
  - `src/aeat/application/workflow/test_engine.py`
  - `src/aeat/entrypoints/cli/workflow/test_cli.py`
  - any new submission helper tests added for `_confirm.py` / `_audit.py`
- Beyond unit tests, inspect the emitted `.aeat/live-submit-audit.log` format in a controlled non-pytest invocation if feasible. If that is not feasible on this branch, document the gap honestly in the execution summary rather than papering over it.
