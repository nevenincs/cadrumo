---
tags:
  - '#research'
  - '#cli-workflow-redesign'
date: '2026-05-12'
modified: '2026-05-12'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
---

# `cli-workflow-redesign` research: `workflow engine harvest`

## Topic

Decide how `WorkflowEngine` is wired into the redesigned modelo filing
lifecycle.

## Audit Surface

The audit covered the apex CLI workflow redesign ADR §8 and §10, the
2026-04-12 workflow-engine ADR/plan/audit, the modelo-file ADR, the
app-modelo-shape ADR, current workflow engine/models/persistence code, current
CLI declaration/modelo surfaces, and workflow tests.

## Rewrite Scope

This research supports a child ADR that decides WorkflowEngine wiring into
`app modelo file`, rejects separate stage verbs, keeps `run_for_period` out of
public CLI, defines exit/error semantics, rejects a standalone workflow root,
and preserves the no-live-submission invariant.

## Finding

`WorkflowEngine` should be harvested as an application-layer lifecycle gate
used by `aeat app modelo file`, not exposed as a standalone CLI root and not
split into per-stage operator verbs.

`run_for_period` remains a public application method but does not become a
public CLI command. Its result is translated at the CLI boundary into
`app modelo file` output, errors, and bucket/modelo events.

## Current Drift

The 2026-04-12 workflow-engine ADR described a ten-stage engine with
`SYNCING_CATALOGUES` and `DRY_RUN_SUBMIT`.

Current `WorkflowStage` has no submit stage. Current runtime behavior is a
read/preflight pipeline that stops after preflight `DONE`; tests pin that no
submission id is created.

The apex currently calls the engine a 5-stage async pipeline, while runtime
behavior has six work stages including draft validation.

Old audit language around dry-run and double-gate submit is outdated. Current
engine has no public `dry_run` or override-confirmation submission path.

Current `app modelo` exists but is introspection-only. Lifecycle behavior still
sits under `app declaration`. No standalone workflow CLI exists.

## Proposed Lifecycle Behavior

`aeat app modelo file` should:

1. Resolve active bucket/profile and target work unit.
2. Require a calculated and verified-complete revision before calling the
   lifecycle gate.
3. Call `WorkflowEngine.run_for_period(profile, modelo, period, today=...)` as
   the read/preflight gate.
4. If the result is `DONE`, create internal filing record and bucket event,
   update the current-filed pointer, and emit text/JSON.
5. If the result is `ABORTED`, create no filing state and emit structured
   failure with stage, reason, summary, and step diagnostics.

`run_next` remains available to application callers but is not harvested into
CLI shape for this ADR. The CLI target is explicit work-unit or
modelo/year/period selection, so `run_for_period` is the correct engine entry.

## Rejected Shapes

- Root `aeat workflow`.
- `aeat app modelo preflight`.
- Per-stage verbs such as `check-inbox`, `validate-draft`, or `run-preflight`.
- `submit`, `presentation`, or live-submit aliases.
- Compatibility shims from old `app declaration file/approve` or `filing`
  paths.

## Output And Event Contract

Use existing `_emit` text/JSON behavior.

Success output includes work-unit id, modelo, year, period, revision,
filing-record id, event id, actor, filed-at, and `internal_file=true`.

Failure output includes error, workflow run id, stage, aborted reason, summary,
and step diagnostics.

CLI usage errors remain parameter errors. Domain gate failures return non-zero
without traceback.

## No-Shim Rule

When `app modelo file` lands, the apex §8 entry is removed rather than adding a
parallel workflow command. Existing `app declaration` lifecycle behavior is
moved or retired per app-modelo-shape; old roots and aliases are not preserved
as transitional shims.
