---
tags:
  - '#research'
  - '#cli-workflow-redesign'
date: '2026-05-12'
modified: '2026-05-12'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
---

# `cli-workflow-redesign` research: `workflow resumption semantics`

## Topic

Decide workflow resumption placement and semantics for the redesigned CLI.

## Audit Surface

The audit covered the apex CLI workflow redesign ADR §6 and §8, the
workflow-engine-harvest ADR, workflow persistence/engine/models/tests, and
run-trace replay behavior.

## Rewrite Scope

This research supports a child ADR that decides `app modelo resume` placement,
continue-vs-replay semantics, the relationship to run-trace replay, idempotency,
output/error contract, the no-workflow-root rule, and the no-shim rule.

## Finding

Resume should be user-facing only as:

```text
aeat app modelo resume <workflow_run_id>
```

The identifier is a workflow-engine run id loaded through workflow persistence,
not an observability or run-trace id.

Resume semantics are continue, not replay. Resume loads a prior terminal
`WorkflowResult`, verifies that it represents an aborted modelo filing with
enough obligation, period, and work-unit context, then starts a new
current-state filing attempt through the app modelo lifecycle.

Resume must not reconstruct historical argv, force old inputs, create a
standalone `aeat workflow` or `aeat run` root, or add compatibility shims.

## Engine And Persistence Constraints

The current workflow engine persists terminal `DONE` or `ABORTED` results. It
does not provide checkpoint cursors or mid-stage continuation. Existing read
and preflight stages do not submit filings.

Persistence can load and list saved terminal workflow results. That is enough
for resume to validate a prior aborted filing and start a new lifecycle run,
but not enough for checkpoint replay.

## CLI Placement

The root remains limited to `config` and `app` entry points. Modelo filing
lifecycle commands belong under `aeat app modelo`.

Apex §6 defers status resume and rejects backlog resume unless an ADR
establishes lifecycle semantics. Apex §8 keeps WorkflowEngine behind the app
modelo file boundary.

## Run Trace Relationship

Run-trace replay remains separate diagnostic and audit functionality. It
reproduces recorded CLI argv with corpus hash gating and `replay_of`.

Observability traces are distinct from workflow runs. Resume creates a new
workflow result linked to the old workflow run through `resumed_from`; it is not
a replay run and does not reconstruct historical argv.

## Contract Notes

Resume accepts only workflow run ids accepted by `load_run`.

It refuses observability or run-trace ids with a typed error.

It requires prior `final_stage` `ABORTED` and enough modelo filing context to
identify the modelo, period, and target work unit.

It re-runs current lifecycle gates from the beginning and never resumes
mid-stage.

It creates a new workflow run id and reports `resumed_from`.

If the target work unit or revision is already filed, resume is idempotent and
creates no new filing record.

If the prior run was `DONE`, resume returns either an already-complete no-op or
a nonzero domain error pointing to app modelo status or history. It must not
duplicate filing state.

Failures are structured, nonzero, and do not print tracebacks. Error output
includes the prior workflow run id, new workflow run id if created, stage,
aborted reason, summary, and diagnostics.
