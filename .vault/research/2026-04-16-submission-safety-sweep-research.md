---
tags:
  - "#research"
  - "#submission-safety-sweep"
date: "2026-04-16"
modified: '2026-04-16'
related:
  - "[[2026-04-16-submission-safety-sweep-reference]]"
  - "[[2026-04-16-live-write-static-audit-reference]]"
  - "[[2026-04-16-live-write-static-audit]]"
  - "[[2026-04-12-submission-engine-research]]"
  - "[[2026-04-12-submission-engine-adr]]"
  - "[[2026-04-12-submission-engine-plan]]"
---

# `submission-safety-sweep` research: `issues-142-146-live-write-hardening`

This research grounds the bundled fix for issues `#142`, `#143`, `#144`, `#145`, and `#146`. The work is a production hardening sweep over the AEAT submission boundary: make live mode explicit, fail-closed under pytest, add the charter-required confirmation and audit surfaces, and remove the misleading stubbed "LIVE OK" CLI path.

## Findings

### Charter and audit baseline

- Issue `#116` is the permanent live-write safety charter. The operative rules for this sweep are:
  - `R2`: every live-capable API must require an explicit keyword-only `dry_run=` choice.
  - `R3`: live writes require a distinct `AEAT_LIVE_SUBMIT_ENABLED=1` gate, separate from `AEAT_LIVE_TESTS_ENABLED`.
  - `R4`: every live write must pass through a blocking exact-phrase confirmation with filing metadata and checksum.
  - `R5`: any `dry_run=False` path must refuse execution when `PYTEST_CURRENT_TEST` is present.
  - `R6`: every live write must append a durable audit record to `.aeat/live-submit-audit.log`.
- The existing audit artifacts `[[2026-04-16-live-write-static-audit-reference]]` and `[[2026-04-16-live-write-static-audit]]` already identify the five concrete gaps later filed as issues `#142` through `#146`.

### Current submission-engine contract

- `SubmissionEngine.submit_draft` and `SubmissionEngine.submit_amendment` still default `dry_run=True` and still expose `override_confirmation=False`.
- The live branch in `SubmissionEngine._submit_with_transport` currently checks only two legacy conditions:
  - caller supplied `override_confirmation=True`
  - `settings.aeat_submission_require_human_confirmation` is truthy
- No production code under `src/aeat/` checks `AEAT_LIVE_SUBMIT_ENABLED`.
- No production code under `src/aeat/` checks `PYTEST_CURRENT_TEST`.
- No `src/aeat/adapters/outbound/aeat/export/_confirm.py` or `src/aeat/adapters/outbound/aeat/export/_audit.py` module exists.

### CLI and amendment drift

- `aeat submission submit` still routes through `aeat.entrypoints.cli.submission._helpers.build_engine()`, which wires `_NullSession` plus stubbed certificate, portal, and justificante providers.
- The command still prints `LIVE submission OK` even though the session factory is not a real AEAT transport.
- `aeat filing complementaria submit --live` reuses `aeat.entrypoints.cli._live.requires_live_enabled()`, which is explicitly a live-test read gate over `AEAT_LIVE_TESTS_ENABLED`, not a live-write gate.
- The same complementaria command still uses `typer.confirm(..., abort=True)` rather than the charter-required exact confirmation phrase.

### Workflow contract drift

- `src/aeat/application/workflow/_protocols.py` still defines `SubmissionEngineProtocol.submit_draft(..., dry_run: bool = True, override_confirmation: bool = False, ...)`.
- `WorkflowEngine.run_next`, `run_for_period`, and `_stage_dry_run_submit` still preserve the legacy `dry_run` default and `override_confirmation` bailout behavior.
- The workflow CLI commands still encode the old `--no-dry-run` + `--i-understand-this-is-real` contract, even though the production workflow helper is intentionally not wired on this branch.

### Real-transport status on this branch

- `aeat.adapters.outbound.aeat.browser.session.BrowserSession` exists, but its auth-backend path inside `create_context()` is still an explicit stub (`pass` after logging).
- There is no existing production helper that wires `SubmissionEngine` to a real Playwright browser session plus the certificate backend for a live filing path.
- Because that transport composition is still incomplete, the safest resolution for issue `#146` on this branch is to fail closed on the CLI live-submit path rather than claim a real live submission succeeded.

## Outcome

- The smallest coherent sweep is engine-first: move live-write authority into `SubmissionEngine`, make `dry_run` explicit everywhere, enforce the new env/pytest/confirmation/audit contract there, and let every caller inherit the same refusal behavior.
- `aeat submission submit` and `aeat filing complementaria submit --live` should remain safety-auditable CLI surfaces, but on this branch they must fail closed for live mode if they still depend on the stubbed `_NullSession` engine factory.
- The workflow package needs signature tightening for `dry_run`, but the workflow CLI does not need new live-write enablement on this branch because its production wiring is already intentionally disabled.
