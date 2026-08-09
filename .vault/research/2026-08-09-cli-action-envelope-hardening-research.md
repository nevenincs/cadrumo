---
tags:
  - '#research'
  - '#cli-action-envelope-hardening'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:e65c2e6dcffea692a40ee713cab004a6baed9fdb990e5ec1da0c7f74344766a6'
related: []
---

# `cli-action-envelope-hardening` research: `Canonical action chains and verb precondition envelopes`

The CLI proves result payloads against registered schemas, but it cannot prove
that a next action comes from the state transition or precondition that produced
it. Command references are free-form prose spread across notices, errors,
workflow details, locales, and tests. Manual dispatch confirmed that this loses
command identity, required argument bindings, and the reason a guarded verb
refused. The evidence favors typed application-owned action and precondition
records projected through the live operator command schema; the ADR must settle
their ownership and migration boundary.

## Findings

### The live envelope types presentation, not an executable action

`Notice.suggestion` and error suggestions are optional strings.
`SCHEMA_REGISTRY` binds a dotted command key only to its result model, while the
operator manifest adds family intent, coarse mutability, and the three-token
`calculate -> verify -> file` lifecycle. Neither declares leaf inputs,
applicable state, failed preconditions, or state-dependent recovery edges. MCP
separately derives leaf input schemas from the live Click tree, proving the
missing pieces can be projected but not assigning semantic ownership.
`src/cadrumo/core/json_contract.py:102`,
`src/cadrumo/core/json_contract.py:221`,
`src/cadrumo/application/operator_surface/_models.py:168`,
`src/cadrumo/application/operator_surface/_models.py:217`,
`src/cadrumo/application/operator_surface/_manifest.py:63`,
`src/cadrumo/entrypoints/mcp/_input_schema.py:1`.

### Clean-room dispatch reproduces prose-only and identity-less recovery

The sweep used a new temporary storage root, file secret store, and JSON output,
so it did not mutate the active profile. On an empty store, `overview status`
returned three next-step notices whose messages embedded commands while every
typed `suggestion` was null. Profile-bound work refusals put the create-profile
action only in prose; three work mutations also reported `command: null`,
`suggestion: null`, `context: null`, and no notices.

A second disposable-store probe created a real profile and dispatched `work
verify` and `work file` against an unknown revision id. Both still reported
`command: null`, `suggestion: null`, and no structured context. Their messages
instructed `work calculate WORK_UNIT_ID`, but the rejected revision id cannot
supply that placeholder, so the proposed action is not executable from the
refusal data. `src/cadrumo/entrypoints/cli/_modelo_work_verification_cli.py:138`,
`src/cadrumo/entrypoints/cli/_modelo_work_verification_cli.py:453`,
`src/cadrumo/entrypoints/cli/_errors.py:730`.

### Guard ordering can erase the verb-specific contract before dispatch

Profile-bound write policy runs before several lazy leaf callbacks resolve. The
policy correctly blocks unsafe work, but its result cannot say which requested
action was guarded, which requirement failed, or whether the proposed recovery
is sufficient. `src/cadrumo/application/storage_write_policy.py:206`,
`src/cadrumo/entrypoints/cli/_common.py:289`.

### Action authority is fragmented across at least seven shapes

Recovery and continuation data lives in error-registry defaults, exception
overrides, `Notice.suggestion`, workflow detail maps, application `next_action`
fields, CLI renderers, and localized prose. Workflow details accept an untyped
value, while the work-runs CLI recognizes selected English strings by equality
to localize them. Other lifecycle renderers author their own continuations.
`src/cadrumo/core/errors/_registry.py:103`,
`src/cadrumo/application/workflow/_models.py:392`,
`src/cadrumo/application/workflow/_engine.py:902`,
`src/cadrumo/entrypoints/cli/_modelo_work_runs_cli.py:67`,
`src/cadrumo/entrypoints/cli/_modelo_work_lifecycle_cli.py:454`,
`src/cadrumo/entrypoints/cli/_modelo_work_verification_cli.py:222`.

The command-citation gate checks whether literals resolve. The real exit-verdict
evaluator improves this with dispatch, but each scenario manually supplies its
expected next action and only checks that the envelope cites it. Neither proves
that the rejecting predicate selected the action, that required arguments are
bound, or that the next verb accepts the resulting state.
`src/cadrumo/entrypoints/cli/tests/test_suggestion_command_conformance.py:329`,
`dev/agent_eval/_models.py:268`, `dev/agent_eval/_runner.py:448`.

### The active profile-diagnostics campaign is upstream, not overlapping authority

`cli-verb-profile-diagnostics` derives missing-profile labels and legal basis
from the profile schema and deliberately leaves refusal verdicts unchanged. Its
plan says every step changes what an operator reads, not whether the verb
refuses. This campaign must reuse that grounding primitive without touching its
in-flight files or unfinished verification.
`.vault/adr/2026-08-09-cli-verb-profile-diagnostics-adr.md:77`,
`.vault/plan/2026-08-09-cli-verb-profile-diagnostics-plan.md:23`,
`.vault/plan/2026-08-09-cli-verb-profile-diagnostics-plan.md:64`.

### Four architecture shapes remain viable

1. A manifest-owned per-leaf contract gives agents one catalogue, but duplicates
   domain predicates unless its conditions only reference application guards.
2. Application state machines and gates can return a typed action outcome with
   action id, command key, argument bindings, failed requirements, and
   conditionality. This gives genuine linkage but requires broad migration.
3. A central action catalogue referenced by existing errors and notices supports
   incremental adoption, but becomes a second policy source if it owns
   applicability instead of resolving application verdicts.
4. Static derivation from Click and registered result schemas validates paths,
   inputs, and outputs, but cannot derive profile, registry, persistence, or
   workflow-state preconditions.

The evidence favors combining options 2 and 3: application-owned typed verdicts
reference one validated action catalogue, while the live CLI schema supplies
the executable projection. The ADR must decide package homes, models, guard
ordering, envelope evolution, and migration slices.

### The campaign must prove both rejection and recovery

A complete gate dispatches a verb with each declared precondition false, asserts
the stable failed-condition identity and grounded evidence, resolves the returned
action against the live leaf schema, proves required placeholders are bound or
explicitly conditional, performs the recovery through real code, and
re-dispatches the original verb. Tests that author the expected transition beside
the assertion are insufficient. Live AEAT writes and destructive storage
operations were not exercised; permanent and safety refusals remain in the
later inventory boundary.

## Sources

- `src/cadrumo/core/json_contract.py:102`
- `src/cadrumo/core/json_contract.py:221`
- `src/cadrumo/core/errors/_registry.py:103`
- `src/cadrumo/application/operator_surface/_models.py:168`
- `src/cadrumo/application/operator_surface/_models.py:217`
- `src/cadrumo/application/operator_surface/_manifest.py:63`
- `src/cadrumo/application/storage_write_policy.py:206`
- `src/cadrumo/application/workflow/_models.py:392`
- `src/cadrumo/application/workflow/_engine.py:902`
- `src/cadrumo/entrypoints/mcp/_input_schema.py:1`
- `src/cadrumo/entrypoints/cli/_common.py:289`
- `src/cadrumo/entrypoints/cli/_errors.py:730`
- `src/cadrumo/entrypoints/cli/_modelo_work_runs_cli.py:67`
- `src/cadrumo/entrypoints/cli/_modelo_work_lifecycle_cli.py:454`
- `src/cadrumo/entrypoints/cli/_modelo_work_verification_cli.py:138`
- `src/cadrumo/entrypoints/cli/_modelo_work_verification_cli.py:222`
- `src/cadrumo/entrypoints/cli/_modelo_work_verification_cli.py:453`
- `src/cadrumo/entrypoints/cli/tests/test_suggestion_command_conformance.py:329`
- `dev/agent_eval/_models.py:268`
- `dev/agent_eval/_runner.py:448`
- `.vault/adr/2026-05-12-cli-workflow-redesign-workflow-resumption-semantics-adr.md:17`
- `.vault/adr/2026-06-10-cli-envelope-notice-standardisation-adr.md:54`
- `.vault/adr/2026-08-09-cli-verb-profile-diagnostics-adr.md:77`
- `.vault/plan/2026-08-09-cli-verb-profile-diagnostics-plan.md:23`
- `.vault/plan/2026-08-09-cli-verb-profile-diagnostics-plan.md:64`
