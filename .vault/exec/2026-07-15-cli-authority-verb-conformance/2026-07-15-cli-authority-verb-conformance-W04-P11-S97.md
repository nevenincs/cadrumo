---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:a35fed8270a7ff4b9b67873f3eab24a6ad7f3baa3bd7e93b4eec9f348dbcd15c'
step_id: 'S97'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Remove the config profile sandbox use registration and execution path without an alias

## Scope

- `src/cadrumo/entrypoints/cli/_config/_sandbox.py`

## Description

Remove the `config profile sandbox use` registration and its execution path, leaving
no alias, hidden registration, or suggestion target behind.

## Outcome

`src/cadrumo/entrypoints/cli/_config/_sandbox.py` registers exactly eight sandbox
leaves and no `use`: `create` (`:79`), `list` (`:162`), `discard` (`:216`), `prune`
(`:349`), `archive` (`:460`), `restore` (`:577`), `usage` (`:653`), and `merge`
(`:744`), all mounted through `register_sandbox_commands` (`:66`). The surviving
`usage` leaf reports disk consumption and is a distinct retained verb, not the
removed `use` door.

No `config.profile.sandbox.use` envelope schema is registered:
`src/cadrumo/entrypoints/cli/_config_sandbox_payloads.py` declares schemas for the
same eight leaves only (`:12`, `:26`, `:50`, `:66`, `:82`, `:96`, `:130`, `:145`).

The unmounting is asserted by `test_config_profile_sandbox_use_door_is_unmounted`
(`src/cadrumo/entrypoints/cli/tests/test_root_grammar_invariants.py:243`), and
`test_retired_reset_and_sandbox_spellings_absent_from_source_and_docs` (`:273`)
extends the check across source and documentation. Both passed in the coordinator's
W04 gate run (`1 failed, 154 passed`; the single failure was the unrelated S112
control).

## Notes

Sandbox selection now happens through `config login` with the canonical
`sandbox:<name>` label rather than a second `use` door — see the sibling record for
S96 and the 2026-07-24 ADR amendment.

`vaultspec-rag` is degraded (truncated code index reporting `degraded_reasons: []`);
all findings were confirmed with `rg` and direct file reads.
