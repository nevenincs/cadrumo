---
tags:
  - '#reference'
  - '#live-submit-safety-sweep'
date: '2026-04-16'
related:
  - '[[2026-04-16-live-write-static-audit-reference]]'
  - '[[2026-04-16-live-write-static-audit]]'
  - '[[2026-04-12-submission-engine-adr]]'
  - '[[2026-04-12-workflow-engine-adr]]'
  - '[[2026-04-13-filing-complementaria-adr]]'
  - '[[2026-04-13-cohesive-project-roadmap]]'
  - '[[2026-04-16-live-write-test-audit-research]]'
  - '[[2026-04-16-live-write-test-audit-adr]]'
---

# `live-submit-safety-sweep` reference: `issue-117-contract-migration`

This reference inventories the concrete code surfaces implicated by the live-submit
safety sweep so the ADR and plan can stay tied to the real contract boundary in
`aeat.submission`, `aeat.workflow`, and the live-capable CLI entrypoints.

## Findings

### Charter mapping

| Charter item | Required outcome | Observed gap |
| --- | --- | --- |
| `R2` | All write-capable surfaces require explicit live intent, with keyword-only `dry_run` under `#117` | Submission and workflow layers still expose permissive defaults around `dry_run=True` and legacy override semantics |
| `R3` | Live writes require `AEAT_LIVE_SUBMIT_ENABLED`; `AEAT_LIVE_TESTS_ENABLED` remains live-read only | Config and env example still model write safety with `AEAT_SUBMISSION_REQUIRE_HUMAN_CONFIRMATION` |
| `R4` | Blocking human confirmation with exact phrase `CONFIRMO FILING {modelo} {period}` and checksum, with no bypass and no pytest reachability | CLI and engine paths still rely on `override_confirmation`, `requires_live_enabled()`, and `typer.confirm(...)` |
| `R5` | Production refuses live writes whenever `PYTEST_CURRENT_TEST` is present | No refusal path is currently described in submission, workflow, or CLI surfaces |
| `R6` | Append-only `.aeat/live-submit-audit.log`; `#117` extends the decision to dry-run attempts | No `_audit` path is currently present in the submission engine |

### Implicated code surfaces

- `src/aeat/submission/_engine.py`
  - Current center of the submission contract.
  - Still defaults `dry_run=True`.
  - Still gates live mode through `override_confirmation` and
    `aeat_submission_require_human_confirmation`.
  - Missing `AEAT_LIVE_SUBMIT_ENABLED`, pytest refusal, `_confirm`, and `_audit`.
- `src/aeat/config.py`
  - Current config surface for submission safety flags.
  - Still models write safety through `AEAT_SUBMISSION_REQUIRE_HUMAN_CONFIRMATION`.
- `env/.env.example`
  - Public env contract still advertises the superseded write-safety variable.
- `tests/test_config.py`
  - Enforces config and env-example alignment and therefore constrains config
    changes to land atomically with env-example edits.
- `src/aeat/cli/submission/submit.py`
  - Still requires `--i-understand-this-is-real`.
  - Still forwards `override_confirmation=True`.
- `src/aeat/cli/submission/_helpers.py`
  - Wires the submission CLI to `_NullSession`.
  - Concentrates the synthetic-live hazard behind issue `#146`.
- `src/aeat/cli/filing/__init__.py`
  - Complementaria submit still uses `requires_live_enabled()` and `typer.confirm(...)`.
- `src/aeat/workflow/_protocols.py`
  - Preserves the old submission API shape with legacy `dry_run` and
    `override_confirmation` expectations.
- `src/aeat/workflow/_adapters.py`
  - Forwards the old contract unchanged into workflow execution.
- `src/aeat/workflow/_engine.py`
  - Continues the same contract at workflow orchestration level.
- `src/aeat/cli/workflow/next.py`
  - Contains duplicated CLI live gating that will need to align with the new contract.
- `src/aeat/cli/workflow/run.py`
  - Contains duplicated CLI live gating that will need to align with the new contract.
- `src/aeat/cli/_live.py`
  - Shared CLI live gating surface that participates in the duplicated boundary.
- `src/aeat/cli/submission/dry_run.py`
  - Direct caller that must remain compatible once `dry_run` becomes required.
- `src/aeat/submission/__init__.py`
  - Docstrings still reflect the old submission boundary and will drift unless
    updated with the new contract language.

### Likely touchpoints

- Core contract touchpoints:
  - `src/aeat/submission/_engine.py`
  - `src/aeat/workflow/_protocols.py`
  - `src/aeat/workflow/_adapters.py`
  - `src/aeat/workflow/_engine.py`
- Config and env touchpoints:
  - `src/aeat/config.py`
  - `env/.env.example`
  - `tests/test_config.py`
- CLI entrypoint touchpoints:
  - `src/aeat/cli/submission/submit.py`
  - `src/aeat/cli/submission/dry_run.py`
  - `src/aeat/cli/submission/_helpers.py`
  - `src/aeat/cli/filing/__init__.py`
  - `src/aeat/cli/workflow/next.py`
  - `src/aeat/cli/workflow/run.py`
  - `src/aeat/cli/_live.py`
- Contract-language touchpoints:
  - `src/aeat/submission/__init__.py`
  - workflow package narrative around live-submit semantics

### Test impact

- Existing tests that currently lock in the old contract:
  - `src/aeat/submission/test_engine.py`
  - `src/aeat/workflow/test_engine.py`
  - `src/aeat/cli/submission/test_cli.py`
- Missing coverage areas introduced by the new charter:
  - `AEAT_LIVE_SUBMIT_ENABLED` gating
  - refusal when `PYTEST_CURRENT_TEST` is present
  - blocking `_confirm` behavior with exact phrase and checksum expectations
  - append-only audit-log behavior
  - the ADR decision on whether dry-run attempts are logged
- Test work for this feature should stay focused on the contract migration and
  should not absorb the broader cleanup tracked in `#150` and `#151`.

### Sequencing constraints

- Settle the submission-engine contract first because it is the dependency root
  for workflow and CLI behavior.
- Move workflow protocol, adapter, and engine surfaces immediately after the
  submission contract changes so they do not continue forwarding the superseded
  shape.
- Coordinate config and env changes atomically with `tests/test_config.py`.
- Update CLI entrypoints as a group after the core contract is stable because
  live gating is duplicated across several command surfaces.
- Resolve the `_NullSession` live-submit hazard early. If the short-term answer
  is to disable CLI live submit until real wiring exists, that should happen
  before any richer confirmation experience is added.
- Record in the ADR that the old `override_confirmation` plus
  `AEAT_SUBMISSION_REQUIRE_HUMAN_CONFIRMATION` boundary is superseded and no
  longer governs the live-write path.
