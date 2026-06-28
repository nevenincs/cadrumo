---
tags:
  - "#audit"
  - "#live-write-static-audit"
date: 2026-04-16
modified: '2026-04-16'
related:
  - "[[2026-04-16-live-write-static-audit-reference]]"
  - "[[2026-04-12-workflow-engine-audit]]"
  - "[[2026-04-13-filing-complementaria-review-audit]]"
---

# live-write-static-audit report

Scope: one-shot static audit for issues #116/#117/#118, limited to the evidence in `2026-04-16-live-write-static-audit-reference` plus the charter scope in #116/#117/#118. No production code changes.

Verdict: HARD NO-GO.

## write-capable entry points

### reachable live write

- `src/aeat/adapters/outbound/aeat/export/_engine.py:94-130` `SubmissionEngine.submit_draft` — reachable live write; still defaults `dry_run=True`, but can dispatch a real submit when explicitly flipped.
- `src/aeat/adapters/outbound/aeat/export/_engine.py:132-170` `SubmissionEngine.submit_amendment` — reachable live write; same default-by-omission risk as `submit_draft`.
- `src/aeat/adapters/outbound/aeat/export/_engine.py:172-247` `SubmissionEngine._submit_with_transport` — reachable live write; live branch still calls the transport submitter at `219-226`.
- `src/aeat/adapters/outbound/aeat/export/_submitters/modelo130.py:163-202` `Modelo130Submitter.submit` — reachable live write; the write leaf is the browser submit click at `190`.
- `src/aeat/application/workflow/_engine.py:201-240` `WorkflowEngine.run_next` — reachable live write through the workflow submit stage.
- `src/aeat/application/workflow/_engine.py:242-278` `WorkflowEngine.run_for_period` — reachable live write through the same workflow submit stage.
- `src/aeat/application/workflow/_engine.py:957-1028` `WorkflowEngine._stage_dry_run_submit` — reachable live write gate; still uses the old `override_confirmation` contract.
- `src/aeat/application/workflow/_adapters.py:135-157,231-289` `SubmissionEngineAdapter.submit_draft`, `default_engine` — reachable live write adapter; passes the submission flags through unchanged.

### latent/stubbed write

- `src/aeat/adapters/outbound/aeat/export/_submitters/modelo130.py:122-161` `Modelo130Submitter.dry_run` — walks the form but aborts before the final submit click.
- `src/aeat/entrypoints/cli/submission/_helpers.py:148-199` `_NullSession` — stub session used by the CLI submission path.
- `src/aeat/entrypoints/cli/submission/_helpers.py:148-199` `build_engine` — wires the CLI submission engine around the null session stub.
- `src/aeat/entrypoints/cli/submission/submit.py:80-115` `submit_cmd` — CLI live mode still routes through the old confirmation flag path.
- `src/aeat/entrypoints/cli/filing/__init__.py:83-85,399-427` `_submission_engine` — helper wiring for submission engine creation.
- `src/aeat/entrypoints/cli/filing/__init__.py:399-427` `submit_complementaria_cmd` — CLI live path still relies on `typer.confirm` plus `override_confirmation`.
- `src/aeat/entrypoints/cli/workflow/_helpers.py:69-159` `_build_engine` — workflow helper wiring, not a direct write leaf.
- `src/aeat/entrypoints/cli/workflow/_helpers.py:69-159` `_build_profile` — workflow helper wiring.
- `src/aeat/entrypoints/cli/workflow/_helpers.py:69-159` `run_engine_next` — workflow CLI wrapper into the staged submit path.
- `src/aeat/entrypoints/cli/workflow/_helpers.py:69-159` `run_engine_for_period` — workflow CLI wrapper into the staged submit path.
- `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/session.py:68-120` `BrowserSession.create_context` — auth-backend branch is a no-op stub.

### read-only

- `src/aeat/domain/justificante/_verify.py:36-105` `verify_csv` — justificante verification only.
- `src/aeat/status/_reader.py:225-337` `fetch_expedientes` — read surface only.
- `src/aeat/status/_reader.py:278-337` `fetch_notificaciones`, `fetch_devoluciones`, `fetch_borrador_irpf`, `fetch_datos_fiscales`, `fetch_calendario` — explicit read stubs that raise `StatusReaderError`.
- `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/session.py:122-157` `BrowserSession.navigate` — navigation helper only.
- `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/health.py:33-47` `run_health_check` — health probe only.
- `src/aeat/application/filing/__init__.py:141-270` `build_draft`, `validate_draft`, `iter_findings`, `utc_now` — draft and validation helpers only.
- `src/aeat/application/filing/_complementaria.py:67-160` `build_complementaria`, `load_amendment`, `list_amendments`, `_persist_amendment` — complementaria persistence/read helpers only.
- `src/aeat/adapters/outbound/aeat/export/_engine.py:249-313` `_persist`, `_persist_amendment_result`, `load_submission`, `list_submissions` — local persistence and read helpers only.

### generic helper

- `src/aeat/config.py:43-501` `Settings`, `load_settings` — configuration surface only.
- `src/aeat/adapters/outbound/aeat/export/_submitters/__init__.py:24-93` `Submitter` — protocol/helper surface only.
- `src/aeat/adapters/outbound/aeat/export/_protocols.py:44-268` protocol and value-model stubs — type surface only.
- `src/aeat/application/workflow/_protocols.py:92-107` `SubmissionEngineProtocol` — protocol surface only.
- `src/aeat/entrypoints/cli/submission/_helpers.py:175-204` `build_engine`, `load_draft` — CLI helper surface only.
- `src/aeat/application/workflow/_adapters.py:231-289` `default_engine` — wiring helper; not itself a direct write leaf.

## gap list

- `src/aeat/adapters/outbound/aeat/export/_engine.py:94-197` `SubmissionEngine.submit_draft` / `submit_amendment` / `_submit_with_transport` — violates R2, R3, R4, R5, R6: `dry_run` is still optional, the live gate still relies on `override_confirmation` plus the old settings flag, no `PYTEST_CURRENT_TEST` refusal exists, no blocking human confirmation hook exists, and no append-only audit log exists.
- `src/aeat/adapters/outbound/aeat/export/_submitters/modelo130.py:163-202` `Modelo130Submitter.submit` — violates R4 and R6: the live write leaf is a browser submit click with no independent human-confirmation function and no audit log append.
- `src/aeat/entrypoints/cli/submission/submit.py:80-115` `submit_cmd` — violates R3 and R4 by routing live mode through the legacy `--i-understand-this-is-real` / `override_confirmation` contract instead of the chartered `AEAT_LIVE_SUBMIT_ENABLED` gate plus a blocking confirmation function.
- `src/aeat/entrypoints/cli/filing/__init__.py:399-427` `submit_complementaria_cmd` — violates R3 and R4: same old live-mode gate, same `typer.confirm` path.
- `src/aeat/application/workflow/_engine.py:201-240`, `242-278`, and `957-1028` (`WorkflowEngine.run_next`, `run_for_period`, `_stage_dry_run_submit`) — violates R2 and R4: workflow submission still defaults through `dry_run` / `override_confirmation` instead of the required hard gate.
- `src/aeat/application/workflow/_adapters.py:135-157,231-289` `SubmissionEngineAdapter.submit_draft` / `default_engine` — violates R2 and R4 by forwarding the old submission contract unchanged.
- `src/aeat/config.py:379-385` and `env/.env.example:185` — violates R3: production still documents `aeat_submission_require_human_confirmation` instead of the distinct `AEAT_LIVE_SUBMIT_ENABLED` gate; no runtime pytest refusal exists in `src/aeat/`.

## filed follow-up issues

- #142 — `SubmissionEngine._submit_with_transport` still lacks the distinct live-submit env gate and pytest refusal (R3, R5).
- #143 — the live submission path still lacks the charter confirmation hook and append-only audit log (R4, R6).
- #144 — `submit_complementaria_cmd` still reuses `AEAT_LIVE_TESTS_ENABLED` and `typer.confirm` for live mode (R3, R4).
- #145 — submission/workflow live-capable APIs still allow omitted `dry_run` (R2).
- #146 — `aeat submission submit` still routes "live" mode through `_NullSession` and reports success, which the audit treats as a latent dead/live hazard.

## dead-code / unreachable findings

- `src/aeat/adapters/outbound/aeat/export/_confirm.py` is absent, so the charter-required confirmation hook is unreachable by construction.
- `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/session.py:112-115` contains a certificate-auth branch that logs and `pass`es; it is a no-op placeholder.
- `src/aeat/status/_reader.py:278-337` contains explicit read-only stubs that raise `StatusReaderError`; they are unreachable as write paths and should not be treated as submission surfaces.
- `src/aeat/entrypoints/cli/workflow/_helpers.py:69-159` is inert for production live-write control because no default workflow engine/profile factory is wired.

## import graph check: `aeat.adapters.outbound.aeat.export._confirm`

- `src/aeat/adapters/outbound/aeat/export/_confirm.py` does not exist.
- No production import edge to `_confirm` exists anywhere under `src/aeat/`.
- Repository-wide search found zero matches for `_confirm` or `request_human_submit_confirmation` outside the reference brief.
- Public `aeat.adapters.outbound.aeat.export` re-exports engine, models, errors, preflight, protocols, and submitter symbols only; it does not expose a confirmation API.

## verdict

HARD NO-GO.

R2-R6 are still violated on main/branch state, the mandatory confirmation hook does not exist, and the write path still relies on the legacy `dry_run` / `override_confirmation` contract instead of the chartered live-submit gate.
