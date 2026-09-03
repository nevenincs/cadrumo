---
tags:
  - '#exec'
  - '#duplication-burndown'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:b5b7d2869b2274ed2f0285f8fb9846ab9614806bf1f1df19c78a4f17a3e30c7d'
step_id: 'S08'
related:
  - "[[2026-09-03-duplication-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Define narrowly typed reusable Ledger parameter declarations and prove immutable CommandSpec equality

## Scope

- `src/cadrumo/entrypoints/cli/_app_ledger_command_spec_support.py`

## Changes

- `M` `src/cadrumo/entrypoints/cli/_app_ledger_command_spec_support.py`
- `A` `src/cadrumo/entrypoints/cli/tests/test_app_ledger_parameter_declaration_primitives.py`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/entrypoints/cli/tests/test_app_ledger_parameter_declaration_primitives.py` -> `pass`
- `verify:` `uv run --no-sync ty check src/cadrumo/entrypoints/cli/_app_ledger_command_spec_support.py` -> `pass`

## Notes

Six primitives were justified by an AST census of the live tree rather than by
resemblance: six keyword shapes account for 200 of the 264 literal parameter
declarations across the ledger command-spec fragments, each recurring in up to 14 files.
Only `name`, `declarations` and `help_key` vary between uses; every remaining field is
fixed by the contract, which is why the primitives supply them.

The shapes are kept separate rather than folded behind default arguments because their
differences are contracts, not detail: an absent default is not an empty-string default,
optional is not required, and a flag is not free text. A gate asserts no two primitives
can collapse onto the same declaration.

Equality is proven against literals constructed independently in the test module, never
against the primitives' own output, and is asserted twice over -- structural equality on
the frozen dataclass, plus a per-field sweep that pins the field set so a field added to
`OptionSpec` later cannot be silently defaulted into every shared parameter. Teeth
confirmed for `show_default`, `hidden`, `multiple`, `is_flag`, `metavar` drift and for a
required-versus-optional swap.

This Step defines the primitives; migrating consumers is the following Steps' scope, so
nothing consumes them yet. That is measurable and is recorded rather than absorbed: the
unreachable-code audit's unused-symbol count moved from 1414 to 1420, exactly these six
functions. The clone count is unchanged at 52 for the same reason -- no literal has been
displaced yet. Both close as the migration Steps land.

`test_root_command_specs.py::test_root_specs_own_the_executable_namespace_and_parameter_contracts`
fails in this worktree on a root parameter tuple (`self_test` versus `quiet`, plus an
extra `debug`). It is unrelated to this Step: nothing in the tree consumes the new
primitives, so this change has no blast radius on the root specs. The failure belongs to
the in-flight CLI root verb work.
