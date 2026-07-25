---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S119'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Require yes for reset start and resume while keeping status non-destructive

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_destructive_verbs_require_yes.py`

## Description

`config reset start`/`resume` and `config auth reset` are non-interactive destructive
operations and must require explicit `--yes`, while `config reset status` (and the
read-only `auth status`/`auth test`) stay non-destructive and need no confirmation flag;
the retired flat `config reset --scope ...` spelling must carry no compatibility parser.

## Outcome

`src/cadrumo/entrypoints/cli/tests/test_destructive_verbs_require_yes.py` proves each half:
`test_config_reset_start_refuses_without_yes` (99-104) and
`test_config_reset_resume_refuses_without_yes` (124-129) both refuse with a non-zero exit
naming `--yes`/confirm; `test_config_reset_status_is_read_only_and_needs_no_yes` (107-111)
succeeds with no flag and reports `operation\t<none>`; `test_auth_reset_refuses_without_yes`
(132-138) refuses `config auth reset --provider certificate` without `--yes`;
`test_auth_status_is_non_destructive_and_needs_no_yes` and
`test_auth_test_is_non_destructive_and_needs_no_yes` (151-178) assert neither `--yes` nor
"confirm" appears in their output, scoping the guard to the destructive reset verb only.
`test_config_reset_removed_scope_spelling_is_rejected` (114-121) proves `config reset
--scope auth --yes` is rejected (the flat scoped spelling carries no alias or compatibility
parser).

## Notes

File matches the step's declared scope exactly. Cited the coordinator's gate run rather
than re-executing (parallel 154 passed/1 failed, serial 27 passed/1 failed, both failures
being the unrelated S112 gap).
