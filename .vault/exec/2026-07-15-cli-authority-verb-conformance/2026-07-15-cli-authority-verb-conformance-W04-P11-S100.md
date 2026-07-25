---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S100'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Replace flat scoped reset registration with the config reset command group

## Scope

- `src/cadrumo/entrypoints/cli/_config/__init__.py`

## Description

Replace the flat `config reset --scope ...` registration with a `config reset`
command group, so reset is addressed by subcommand rather than by a scope flag.

## Outcome

`src/cadrumo/entrypoints/cli/_config/__init__.py` imports `register_reset_commands`
from the dedicated module (`:54`) and mounts the group onto the config app at
`:1351`, re-exporting the registrar at `:1381`. No flat reset command and no
`--scope` option remain on the config app.

The removal is complete at the contract level: `rg` for `ResetScope`,
`reset.*--scope`, and `RESET_SCOPE` across `src/cadrumo` and `docs` (excluding test
trees) returns no production match, so the DATA/AUTH scope vocabulary the ADR retires
has no residual enum, payload field, or documentation path.

Asserted by `test_config_reset_registers_exactly_start_status_resume`
(`src/cadrumo/entrypoints/cli/tests/test_root_grammar_invariants.py:209`) and
`test_config_reset_rejects_the_retired_scope_flag` (`:226`); both passed in the
coordinator's W04 gate run (`1 failed, 154 passed`, the single failure being the
unrelated S112 control).

## Notes

The reset verb prefix `config reset` remains in the profile-bound write guard
`PROFILE_BOUND_WRITE_VERB_PATHS` (`src/cadrumo/application/storage_write_policy.py:186`).
That catalog is matched by prefix, so the group's `start`, `status`, and `resume`
leaves all stay guarded without needing three separate entries — the hand-sweep of
that unscanned surface confirmed no dead entry and no dropped coverage.

`vaultspec-rag` is degraded (truncated code index reporting `degraded_reasons: []`);
all findings were confirmed with `rg` and direct file reads.
