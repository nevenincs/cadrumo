---
tags:
  - "#reference"
  - "#live-write-static-audit"
date: "2026-04-16"
modified: '2026-04-16'
related:
  - "[[2026-04-12-workflow-engine-audit]]"
  - "[[2026-04-13-filing-complementaria-review-audit]]"
---

# live-write-static-audit reference brief

Scope: `src/aeat/` production code only, centered on `aeat.adapters.outbound.aeat.export`, `aeat.application.workflow`, `aeat.entrypoints.cli.submission`, `aeat.entrypoints.cli.filing`, `aeat.adapters.outbound.aeat.browser`, `aeat.domain.justificante`, `aeat.status`, `aeat.core.config`, `env/.env.example`, and issues #116/#117/#118.

## High-signal read
- No direct `requests.*` or `httpx.*` write calls were found under `src/aeat/`.
- The AEAT-side write leaf is the browser submit click in `Modelo130Submitter.submit`.
- The CLI submission/amendment commands are stubbed through `_NullSession`, so their current "live" mode is not a real AEAT transport.
- `src/aeat/adapters/outbound/aeat/export/_confirm.py` does not exist, so the charter-required confirmation hook is absent by construction.

## Entry point inventory

### Reachable live write
- `src/aeat/adapters/outbound/aeat/export/_engine.py:94-130` `SubmissionEngine.submit_draft`
- `src/aeat/adapters/outbound/aeat/export/_engine.py:132-170` `SubmissionEngine.submit_amendment`
- `src/aeat/adapters/outbound/aeat/export/_engine.py:172-247` `SubmissionEngine._submit_with_transport` (`submitter.submit` live branch at `219-226`)
- `src/aeat/adapters/outbound/aeat/export/_submitters/modelo130.py:163-202` `Modelo130Submitter.submit` (`session.click("button#firmar-y-enviar")` at `190`)
- `src/aeat/application/workflow/_engine.py:201-240` `WorkflowEngine.run_next`
- `src/aeat/application/workflow/_engine.py:242-278` `WorkflowEngine.run_for_period`
- `src/aeat/application/workflow/_engine.py:957-1028` `WorkflowEngine._stage_dry_run_submit`
- `src/aeat/application/workflow/_adapters.py:135-157, 231-289` `SubmissionEngineAdapter.submit_draft`, `default_engine`

### Latent or stubbed write
- `src/aeat/adapters/outbound/aeat/export/_submitters/modelo130.py:122-161` `Modelo130Submitter.dry_run` walks the form but aborts before the final submit click.
- `src/aeat/entrypoints/cli/submission/_helpers.py:148-199` `_NullSession`, `build_engine`
- `src/aeat/entrypoints/cli/submission/submit.py:80-115` `submit_cmd`
- `src/aeat/entrypoints/cli/filing/__init__.py:83-85, 399-427` `_submission_engine`, `submit_complementaria_cmd`
- `src/aeat/entrypoints/cli/workflow/_helpers.py:69-159` `_build_engine`, `_build_profile`, `run_engine_next`, `run_engine_for_period`
- `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/session.py:68-120` `BrowserSession.create_context` auth backend branch is a no-op stub

### Read-only
- `src/aeat/domain/justificante/_verify.py:36-105` `verify_csv`
- `src/aeat/status/_reader.py:225-337` `fetch_expedientes` and the unimplemented `fetch_*` read surfaces
- `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/session.py:122-157` `BrowserSession.navigate`
- `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/health.py:33-47` `run_health_check`
- `src/aeat/application/filing/__init__.py:141-270` `build_draft`, `validate_draft`, `iter_findings`, `utc_now`
- `src/aeat/application/filing/_complementaria.py:67-160` `build_complementaria`, `load_amendment`, `list_amendments`, `_persist_amendment`
- `src/aeat/adapters/outbound/aeat/export/_engine.py:249-313` `_persist`, `_persist_amendment_result`, `load_submission`, `list_submissions`

### Generic helpers
- `src/aeat/config.py:43-501` `Settings`, `load_settings`
- `src/aeat/adapters/outbound/aeat/export/_submitters/__init__.py:24-93` `Submitter`
- `src/aeat/adapters/outbound/aeat/export/_protocols.py:44-268` protocol and value-model stubs
- `src/aeat/application/workflow/_protocols.py:92-107` `SubmissionEngineProtocol`
- `src/aeat/entrypoints/cli/submission/_helpers.py:175-204` `build_engine`, `load_draft`

## Charter mapping
- R2: violated. `SubmissionEngine.submit_draft` and `submit_amendment` still default `dry_run=True` (`src/aeat/adapters/outbound/aeat/export/_engine.py:94-139`), and the workflow protocol/adapters still default `dry_run=True` / `override_confirmation=False` (`src/aeat/application/workflow/_protocols.py:99-107`, `src/aeat/application/workflow/_adapters.py:135-149`).
- R3: violated. The only submission gate in production is `aeat_submission_require_human_confirmation` in `src/aeat/config.py:379-385`, with `AEAT_SUBMISSION_REQUIRE_HUMAN_CONFIRMATION` still documented in `env/.env.example:185`; no `AEAT_LIVE_SUBMIT_ENABLED` or `PYTEST_CURRENT_TEST` guard exists in `src/aeat/`.
- R4: violated. The live path uses `override_confirmation` and `typer.confirm` (`src/aeat/entrypoints/cli/submission/submit.py:80-112`, `src/aeat/entrypoints/cli/filing/__init__.py:411-418`) instead of a blocking confirmation function, checksum, and exact phrase prompt.
- R5: violated. No production file under `src/aeat/` checks `PYTEST_CURRENT_TEST`; the only live-test gating remains `AEAT_LIVE_TESTS_ENABLED` in `src/aeat/entrypoints/cli/_live.py:33-36`.
- R6: violated. Submission persistence writes to `aeat_submissions_dir` and `aeat_submissions_dir/amendment-results` (`src/aeat/adapters/outbound/aeat/export/_engine.py:249-263`) rather than an append-only `.aeat/live-submit-audit.log`; no audit-log writer exists.

## Drift versus #117
- `dry_run` is still optional instead of required keyword-only, so omission remains possible.
- The env gate is still `AEAT_SUBMISSION_REQUIRE_HUMAN_CONFIRMATION`, not the required `AEAT_LIVE_SUBMIT_ENABLED`.
- There is no `src/aeat/adapters/outbound/aeat/export/_confirm.py` and no `src/aeat/adapters/outbound/aeat/export/_audit.py`.
- The CLI live paths still depend on `_NullSession` or test hooks, so the live-writer hardening from #117 is not wired.
- The requested new error types (`AeatLiveSubmitNotEnabledError`, `AeatPytestLiveWriteRefusedError`, `AeatLiveSubmitConfirmationRefusedError`) do not exist.

## Import graph for `aeat.adapters.outbound.aeat.export._confirm`
- `src/aeat/adapters/outbound/aeat/export/_confirm.py` is absent.
- No production import edge to `_confirm` exists anywhere under `src/aeat/`.
- Search result: zero matches for `_confirm` or `request_human_submit_confirmation` in production code.
- `aeat.adapters.outbound.aeat.export` currently re-exports `_engine`, `_submitters`, and protocol/model symbols only (`src/aeat/adapters/outbound/aeat/export/__init__.py:25-60`).

## Dead or unreachable paths
- The charter-required confirmation hook is unreachable because the module does not exist.
- `src/aeat/status/_reader.py:278-337` contains explicit read-only stubs (`fetch_notificaciones`, `fetch_devoluciones`, `fetch_borrador_irpf`, `fetch_datos_fiscales`, `fetch_calendario`) that raise `StatusReaderError`; they are not write paths.
- `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/session.py:112-115` contains a certificate-auth branch that logs and `pass`es, so it is a no-op placeholder.

## Candidate follow-up issues
- `src/aeat/adapters/outbound/aeat/export/_engine.py:94-197` (`submit_draft`, `submit_amendment`, `_submit_with_transport`) violates R2, R3, R4, R5, and R6.
- `src/aeat/adapters/outbound/aeat/export/_submitters/modelo130.py:163-202` (`Modelo130Submitter.submit`) violates R4 and R6 if called directly as a live leaf.
- `src/aeat/entrypoints/cli/submission/submit.py:80-115` (`submit_cmd`) violates R3 and R4; it also uses a stubbed browser session via `src/aeat/entrypoints/cli/submission/_helpers.py:148-199`.
- `src/aeat/entrypoints/cli/filing/__init__.py:399-427` (`submit_complementaria_cmd`) violates R3 and R4; it also flows through the same stubbed engine.
- `src/aeat/application/workflow/_engine.py:201-240`, `242-278`, and `957-1028` (`run_next`, `run_for_period`, `_stage_dry_run_submit`) violate R2 and R4 and still reflect the old `override_confirmation` gate.
- `src/aeat/config.py:379-385` and `env/.env.example:97,185` violate R3 because they still model live-submit safety with the wrong env variable.
- `src/aeat/entrypoints/cli/workflow/_helpers.py:69-159` (`_build_engine`, `_build_profile`, `run_engine_next`, `run_engine_for_period`) is currently inert for production because no default workflow engine/profile factory is wired.
