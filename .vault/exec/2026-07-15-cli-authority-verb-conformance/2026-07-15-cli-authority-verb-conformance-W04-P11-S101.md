---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S101'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Register only reset start, status, and resume with operation, retention, reason, and confirmation options

## Scope

- `src/cadrumo/entrypoints/cli/_config/_reset_cli.py`

## Description

Register exactly three reset leaves — `start`, `status`, `resume` — carrying the
operation-id, retention-override, reason, and confirmation options, and nothing else.

## Outcome

`src/cadrumo/entrypoints/cli/_config/_reset_cli.py` declares exactly three
`@reset_app.command(...)` registrations, at `:114`, `:145`, and `:176`, mounted by
`register_reset_commands` (`:227`) and exported with `reset_app` (`:232`).

The option set is present and typed: `--yes` as `_YesOpt` (`:50`),
`--override-retention` (`:54`), `--reason` (`:64`), and `--operation-id` (`:156`).
The retention pairing is validated rather than silently accepted —
`_retention_override` (`:34`) refuses an override without a non-empty `--reason`
(`:37`) and refuses a `--reason` supplied without `--override-retention` (`:42`),
each raising with the offending option named in `context`. `_require_yes_and_override`
(`:78`) refuses first on a missing `--yes`, then validates the pairing, so a
destructive reset cannot proceed unconfirmed.

Asserted by `test_config_reset_registers_exactly_start_status_resume`
(`src/cadrumo/entrypoints/cli/tests/test_root_grammar_invariants.py:209`), green in
the coordinator's W04 gate run (`1 failed, 154 passed`; the single failure was the
unrelated S112 control).

## Notes

`status` takes `--operation-id` but no `--yes`, keeping the read-only leaf
non-destructive as the ADR requires; the `--yes` requirement on `start` and `resume`
is separately proven by S119.

`vaultspec-rag` is degraded (truncated code index reporting `degraded_reasons: []`);
all findings were confirmed with `rg` and direct file reads.
