---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S121'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Remove modelo audit replay and every call to the backend replay method while retaining only genuine evidence audit check

## Scope

- `src/cadrumo/entrypoints/cli/_modelo_audit_cli.py`

## Description

Remove `modelo audit replay` and every call to the backend replay method, retaining
only the genuine evidence `audit check`.

## Outcome

`src/cadrumo/entrypoints/cli/_modelo_audit_cli.py` registers exactly three audit
leaves and no `replay`: `show` (`@audit_app.command` at `:34`, handler `audit_show`
at `:41`), `check` (`:85` / `audit_check` at `:92`), and `export` (`:127` /
`audit_export` at `:134`), mounted by `register_audit_commands` (`:23`). The module
makes no call to a backend replay method — `rg` for `replay` across
`src/cadrumo/entrypoints/cli/` returns matches only in `registry.py` and in test
files.

The `registry.py` matches are a distinct retained verb: `registry parity replay`
(`src/cadrumo/entrypoints/cli/registry.py:529`, envelope
`command="registry.parity.replay"` at `:556`) is the registry oracle-replay parity
tool, not the retired modelo audit door. It is deliberately out of this step's scope.

No replay envelope schema is registered for audit: the only `replay` schema
registration in the tree is `registry.parity.replay`
(`src/cadrumo/entrypoints/cli/_registry_payloads.py:184`).

Absence is asserted by `test_audit_replay_command_is_removed`
(`src/cadrumo/entrypoints/cli/tests/test_audit_verbs.py:142`) and
`test_audit_replay_result_schema_is_not_registered` (`:151`), and at the root surface
by `test_modelo_audit_verbs_only_register_canonical_three`
(`src/cadrumo/entrypoints/cli/tests/test_root_grammar_invariants.py:86`). All passed
in the coordinator's W04 gate run (`1 failed, 154 passed`; the single failure was the
unrelated S112 control).

## Notes

The ADR's rationale for the removal is that audit replay was exactly audit check
under a second, weaker name — the retained `check` is the genuine evidence
verification, so no capability was lost with the door.

`vaultspec-rag` is degraded (truncated code index reporting `degraded_reasons: []`);
all findings were confirmed with `rg` and direct file reads.
