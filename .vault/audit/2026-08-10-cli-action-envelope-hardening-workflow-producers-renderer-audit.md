---
tags:
  - '#audit'
  - '#cli-action-envelope-hardening'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:b124e72c6471be0a3bcc63cf3d7506202834ec43cb134b22255792a2b989e6a5'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
  - "[[2026-08-09-cli-action-envelope-hardening-adr]]"
---

# `cli-action-envelope-hardening` audit: `S22-S23 typed workflow producer and renderer review`

## Scope

Fresh-context review of commits `ceedff5c02`, `9f4cb804f7`, and
`3961e32daa` against the accepted action-envelope ADR and the S21-S23 plan
boundary. The review covered the closed workflow models, v3 encrypted run
persistence and resume paths, every workflow engine refusal producer,
`ModeloWorkflowGateError`, the `modelo.work.runs` result projection, the four
locale catalogues, and their direct tests. It also checked the committed diff
for forbidden fake, mock, patch, skip, and xfail shortcuts and for concurrent
worktree ownership leakage.

The selected model, persistence, resume, gate-error, and CLI suites passed 76
tests; 13 integration-marked cases were deselected by the repository's active
unit-lane marker. A direct production-model probe then constructed an actionable
workflow verdict. The persisted verdict retained
`operator.modelo.work.calculate`, but the rendered gate error emitted
`action: null` and the run-list row emitted no action field. This is the
uncovered producer-to-projection failure recorded below.

## Findings

### resumable-terminal-verdict | high | Resumable operational aborts are classified as terminal

`src/cadrumo/application/workflow/_engine_recording.py:67,95,106-120`
assigns `NoRecoveryOutcome.TERMINAL` to both `SITE_UNAVAILABLE` and
`UNHANDLED_EXCEPTION`. The resume authority at
`src/cadrumo/application/workflow/_resume.py:99-105` declares only
`NO_PENDING_OBLIGATION`, `ALREADY_FILED`, and `USER_CANCELLED` non-resumable, so
those operational aborts remain valid resume inputs. A terminal no-recovery
verdict therefore contradicts the workflow's own state transition. The resume
tests conceal the mismatch by constructing terminal verdicts for generic abort
reasons rather than exercising the real site-unavailable producer through
persistence and resume.

### gate-action-projection | high | Workflow gate errors discard the persisted typed verdict

`src/cadrumo/application/modelo/_action_errors.py:151-165` retains the full
`WorkflowResult` only on `ModeloWorkflowGateError`'s private telemetry property
and exposes no canonical precondition-verdict projection to the CLI error
boundary. `_emit_error_and_exit` at
`src/cadrumo/entrypoints/cli/_errors.py:780-811` therefore receives no policy
projection for this exception and serializes `action: null`, even when the
terminal workflow step carries an actionable `PreconditionVerdict`. The change
removed the legacy suggestion, which is correct, but supplied no typed
replacement at the refusal boundary. This breaks the ADR's requirement that
the same application-owned verdict that refused the operation reach the error
envelope.

### run-list-action-projection | high | Work-run history drops typed recovery actions instead of resolving them

`src/cadrumo/entrypoints/cli/_modelo_work_runs_cli.py:73-89` renders only the
locale-key summary and
`src/cadrumo/entrypoints/cli/_modelo_aux_payloads.py:151-173` gives
`WorkflowRunPayload` no typed action field. Consequently an actionable
persisted terminal verdict disappears from both JSON and text history output.
The direct CLI tests assert removal of `next_action` but never assert a
schema-resolved successor, so they currently enshrine the information loss.
Removing English string equality and the legacy `next_action` column is an
intentional breaking change; replacing it with no action projection is not the
accepted producer-to-projection architecture. The divergent fixture and
information-loss assertions are at
`src/cadrumo/entrypoints/cli/tests/test_work_resume.py:164-200,275-306`.

### locale-commit-scope | low | Workflow locale commit also absorbed unrelated TUI catalogue drift

Commit `9f4cb804f7` includes the intended workflow summary keys and retired
workflow command prose, but it also commits unrelated `flows` catalogue changes
for choice, field, namespace, review, section, and status rendering in all four
languages. The user-authorized WIP sweep explains why those bytes needed a
commit, but the workflow-only subject under-describes their ownership and makes
later domain-level archaeology less reliable.

### persistence-version-description | low | Current persistence documentation still names the retired v2 contract

The namespace registry at
`src/cadrumo/adapters/persistence/storage/_namespace_registry.py:32,268-274`
and refusal tests correctly require workflow-run schema v3 and reject v2 on
both direct and enumerated reads. The validation helper's docstring at
`src/cadrumo/application/workflow/_persistence.py:520` still calls the current
contract v2, while the S21 execution record's
description and outcome also say the step advanced to v2. Those statements are
now stale and conflict with the live v3 boundary.

## Recommendations

For `resumable-terminal-verdict`, make operational failure verdicts agree with
the resume authority. Prefer a canonical typed resume or retry action when it
can be bound; otherwise use the honest non-terminal closed outcome selected by
the application contract. Add a real site-health producer-to-persistence-to-
resume test and a retry proof instead of manufacturing the expected verdict in
the test fixture.

For `gate-action-projection`, add one boundary adapter that resolves the terminal
workflow step's `PreconditionVerdict` against the live action catalogue and
passes the resulting `ResolvedPreconditionAction` into the existing error
envelope. Keep the live `WorkflowResult` out of public exception context and add
a real JSON CLI refusal test proving action identity, conditionality, missing
bindings, and target command schema.

For `run-list-action-projection`, extend each workflow-run row with the shared
resolved precondition-action DTO, or another existing canonical wire DTO with
identical semantics. Render text command guidance only from that resolved DTO.
Add four-language CLI coverage that proves the human summary varies while the
action identity and binding facts remain byte-stable. Do not restore
`next_action`, mapping compatibility, raw command prose, or English equality
matching.

For `locale-commit-scope`, retain the committed bytes but record the additional
TUI/status catalogue ownership in the handoff or a follow-up commit message so
the WIP sweep remains traceable.

For `persistence-version-description`, update the stale v2 wording through the
VaultSpec-owned lifecycle/documentation path without changing the already
correct v3 runtime behavior.
