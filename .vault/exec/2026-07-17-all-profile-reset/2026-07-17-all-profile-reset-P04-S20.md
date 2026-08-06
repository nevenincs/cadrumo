---
tags:
  - '#exec'
  - '#all-profile-reset'
date: '2026-07-19'
modified: '2026-07-19'
body_hash: 'sha256:d55fb13b392accd48c6a05402364b7f45d3e04264f3b7919d306581d653e67e1'
step_id: 'S20'
related:
  - "[[2026-07-17-all-profile-reset-plan]]"
---

# Replace flat scoped reset registration with the config reset command group

## Scope

- `src/cadrumo/entrypoints/cli/_config/__init__.py`

## Description

- Delete the flat `app.command("reset", ...)` scoped-reset verb (`config_reset`, `--scope`/`--yes` options, the `_CONFIG_RESET_SCOPE_CHOICE` click bridge) from `_config/__init__.py`.
- Mount `register_reset_commands(app)` from the new `_reset_cli.py` command group, replacing the deleted verb one-for-one.

## Outcome

Verified against HEAD (`8af409cd3f`), not re-implemented; landed by commit `38eba09021` ("refactor(config): hard-cut reset CLI lifecycle").
`git show 38eba09021 -- src/cadrumo/entrypoints/cli/_config/__init__.py` shows the flat `@app.command("reset", ...)` function, its `_CONFIG_RESET_SCOPE_CHOICE` cast bridge, and the `CONFIG_RESET_SCOPE_CLI_VALUES`/`parse_config_reset_scope` imports fully removed (a hard cut, no alias), and `from ._reset_cli import register_reset_commands` / `register_reset_commands(app)` added in their place. `rg -n '"reset"' src/cadrumo/entrypoints/cli/_config/*.py` at HEAD finds no other flat scoped-reset registration — the only remaining `"reset"` command is the unrelated `config auth reset` provider-credential verb. `test_config_reset_removed_scope_spelling_is_rejected` (`test_destructive_verbs_require_yes.py:114`) proves `config reset --scope auth --yes` is rejected (no compatibility parser).

## Notes

No incidents. This step was landed out of plan order relative to P04.S18/S19 (switch/sandbox-use restriction), which remain open; the CLI door and reset-family cutover proceeded independently of the sandbox-label hardening.
