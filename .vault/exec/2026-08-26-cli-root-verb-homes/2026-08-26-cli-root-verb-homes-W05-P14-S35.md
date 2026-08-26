---
tags:
  - '#exec'
  - '#cli-root-verb-homes'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:2f79f708525e15891beb5ccee2aea65273b9f2a1bd1df5caf8e3a7c982f74a7f'
step_id: 'S35'
related:
  - "[[2026-08-26-cli-root-verb-homes-plan]]"
---

# Run the full suite sequentially and reconcile the vault

## Scope

- `src/cadrumo/`

## Changes

- `M` `src/cadrumo/entrypoints/cli/_command_spec.py`
- `M` `src/cadrumo/entrypoints/cli/tests/test_app_family_command_spec_demand_loading.py`
- `M` `src/cadrumo/entrypoints/cli/tests/test_app_ledger_command_specs.py`
- `M` `src/cadrumo/entrypoints/cli/tests/test_command_graph_consumers.py`
- `M` `src/cadrumo/entrypoints/cli/tests/test_modelo_nonwork_command_specs.py`
- `M` `src/cadrumo/entrypoints/cli/tests/test_modelo_spreadsheet_pull_flag.py`
- `M` `src/cadrumo/entrypoints/cli/tests/test_modelo_spreadsheet_pull_observations.py`
- `M` `src/cadrumo/entrypoints/cli/_config/tests/test_google_command_specs.py`
- `verify:` `pytest src/cadrumo/entrypoints/cli (sequential)` -> `1426 passed, 30 failed (all peer-owned)`

## Notes

The suite went 50 -> 35 -> 30 failures across three passes; all 20 failures this
campaign owned are fixed and the remaining 30 trace to concurrent peer work:
`cadrumo.application.wizard` and `cadrumo.application.modelo` inert package
namespaces (17), the modelo-200 `2025-y-siguientes` registry split (4),
`LedgerIssuePayload` gaining an `operator_action` field (1), output-surface
exemptions keyed to modules the peer renamed (2), and passphrase-channel
refusals in a non-TTY environment (3). Three further modules are excluded from
the run entirely because peer renames broke their imports at collection
(`sessionless_root_fixtures`, `cli:_errors`).

Two defect classes this Step exposed are worth carrying forward. First, a
find-and-replace sweep cannot tell a RENAME from a MOVE or a DELETION: four
exact-set census modules carried keys like `config_modelo_spreadsheet_cli_pull`
for leaves that had left the family entirely. Second, `_command_spec.py` is
probed by `runpy.run_path` in a bare interpreter with no package context, so the
relative core import added in W01.P01.S02 broke it; the absolute form satisfies
the probe because `core/transport_locus.py` imports nothing but `enum`.

`test_modelo_spreadsheet_pull_observations` asserted a relative-import DEPTH
(`node.level == 4`) rather than a name. Moving the handler out of `_config/`
necessarily invalidated it, and no rename sweep could have caught that.

This record covers work done TOWARD the Step; the Step itself remains OPEN, and
its heading promises more than this record delivers. The row has since been
rewritten to describe bounded per-package slices, because a single sequential
full-tree pass does not complete in this worktree: one died at 20 per cent after
fifty minutes with no summary, and a `domain`-only slice reached 7 per cent in
fifteen. The slices that did complete are recorded in the fourth addendum of the
close honesty audit -- `entrypoints/cli` 1426 passed / 28 failed, `core` 2234
passed / 19 failed, campaign-touched non-CLI 10 passed / 2 failed, every failure
traced to peer work.

What the standing goal still asks for that this excludes: a single pass over the
whole tree. It is not achievable here while six modules fail at collection from
the peers' in-flight relocation, since one broken import aborts the entire run.
