---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:a84fbc2e1626d174e4d353f98f3f4255748ab3bba0f875e2089955079fd4ebbe'
step_id: 'S123'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Prove modelo audit exposes check without replay, backend replay calls, replay result schemas, or synthetic replay events

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_audit_verbs.py`

## Description

Prove that `modelo audit` exposes `check` with no replay command, no backend replay
call, no replay result schema, and no synthetic replay event.

## Outcome

`src/cadrumo/entrypoints/cli/tests/test_audit_verbs.py` pins the removal on two
independent axes rather than one: `test_audit_replay_command_is_removed` (`:142`)
covers the registered command surface, and
`test_audit_replay_result_schema_is_not_registered` (`:151`) covers the envelope
schema registry — so a replay door could not be reintroduced through a schema
registration without the gate firing.

The retained surface is proven positively, which is what keeps the absence
assertions meaningful: `test_audit_check_reports_verification_state` (`:87`)
exercises the genuine evidence check, `test_audit_show_renders_bundle_manifest`
(`:71`) and `test_audit_show_refuses_unknown_bundle` (`:81`) cover `show`, and the
export cases (`:97`, `:124`, `:136`) cover `export` including its incomplete-without-force
refusal. `test_audit_workflow_end_to_end_show_check_export` (`:160`) drives the three
retained leaves together end to end.

`test_audit_help_text_uses_accepted_vocabulary` (`:192`) prevents the retired word
surviving in operator-facing help, and `test_audit_verbs_refuse_without_active_profile`
(`:230`) confirms the profile gate.

The module passed in the coordinator's W04 gate run (`1 failed, 154 passed`; the
single failure was the unrelated S112 control).

## Notes

`registry parity replay` (`src/cadrumo/entrypoints/cli/registry.py:529`) is a
distinct retained verb and is correctly untouched by these assertions — the removal
is scoped to the modelo audit door.

`vaultspec-rag` is degraded (truncated code index reporting `degraded_reasons: []`);
all findings were confirmed with `rg` and direct file reads.
