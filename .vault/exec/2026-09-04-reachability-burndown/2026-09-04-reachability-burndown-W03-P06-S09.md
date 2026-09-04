---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:705bd66b24fcb1253470dab959bfd01328e625ca6b0a441cfb56bc03afaf20f9'
step_id: 'S09'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Resolve the entrypoints/cli symbol concentration without altering command contracts

## Scope

- `src/cadrumo/entrypoints/cli`

## Changes

- `M` `src/cadrumo/entrypoints/cli/command_spec.py`
- `M` 24 CLI command-spec and support modules repointed onto the canonical contracts
- `A` `src/cadrumo/entrypoints/cli/tests/test_builtin_value_contracts_are_canonical.py`
- `M` `dev/audit/reachability_classification.toml`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/entrypoints/cli/tests/test_builtin_value_contracts_are_canonical.py` -> `pass`
- `verify:` `uv run --no-sync ty check src/cadrumo/entrypoints/cli/` -> `pass`

## Notes

Twenty-five modules each declared their own `ValueContract(DeferredTarget("builtins", ...))`
for str, int or bool, under ELEVEN different local names: `_STR`, `_INT`, `_BOOL`,
`_TEXT_VALUE`, `_WHOLE_NUMBER_VALUE`, `_FLAG_VALUE`, `_STRING`, `_STRING_VALUE`,
`_OPTIONAL_STRING`, `_MODELO_OPEN` and `_INTEGER_VALUE`. The value is immutable and carries
no per-module state, so every copy was a duplicate definition rather than a convenience.

`TEXT_VALUE`, `WHOLE_NUMBER_VALUE` and `FLAG_VALUE` now live in `command_spec` beside
`ValueContract` itself -- the module that defines the type is the canonical home -- and
every use site was repointed to the canonical name rather than left aliasing a shared
value under a local one. Two of the displaced copies were this campaign's own: the
`_TEXT_VALUE` and `_FLAG_VALUE` pairs added to the ledger and modelo parameter support
modules during the duplication work, which had created a third home for the same concept.

Equivalence is proven across the whole package rather than per module: all 133 exported
command-spec tuples hash to
`sha256:5512cffa1766098951c774d9ce18f322c025d881a7371272501cf86c9cc5bfd5` before and after.

## Notes on the gate

A name-based sweep found nineteen modules. The value-based gate written afterwards
immediately found six more, under names no rename map would have guessed --
`_STRING_VALUE`, `_INTEGER_VALUE`, `_MODELO_OPEN`, `_STRING`, `_OPTIONAL_STRING`. That is
the argument for gating on the VALUE a module constructs rather than the name it binds:
the duplicate that hides is the one named differently.

Teeth proven by reintroducing a local `_STR` into a migrated module: the gate exits 1 and
names the offending file, and exits 0 once restored. The first teeth attempt injected the
copy above its own import and produced a collection error rather than a failure, which is
not the same signal and was redone.

The 19 CLI test failures in this worktree are pre-existing. Proven by A/B on the full CLI
suite against copies of all nineteen unmodified modules: 19 failed and 1361 passed
identically with and without the migration.
