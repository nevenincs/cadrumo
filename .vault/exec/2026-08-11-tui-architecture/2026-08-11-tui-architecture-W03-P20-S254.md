---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:2d7a09dbd7c887a64cb6e656f394cbb0063a426865a7559cd720ba9b8ddc76dd'
step_id: 'S254'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Prove the registry package fixed point: zero project package bindings, zero re-exports, and zero unresolved family rows

## Scope

- `src/cadrumo/domain/calculations/registry/__init__.py`

## Changes

M src/cadrumo/domain/calculations/registry/tests/test_keep_public_family.py
M dev/quality/registry_facade_family_census.v1.json

<!-- MECHANICAL LOG. One line per path touched, nothing else:
       `A path` added   `M path` modified   `D path` deleted   `R old -> new` renamed
     Paths are repo-relative, in backticks. No prose, no sentences, no
     narration of intent, outcome, or difficulty - the diff and the plan Step
     already carry those. Example:

       - `M` `src/vaultspec_core/cli/exec_cmd.py`
       - `A` `src/vaultspec_core/cli/tests/test_exec_cmd.py`
       - `D` `src/legacy/shim.py`

     Optional final line, only when a check was run:
       - `verify:` `<command>` -> `pass` | `fail`

     Optional `## Notes` section, ONLY on exception: data loss, skipped work,
     a scaffold left in code, or a persistent failure. Omit it otherwise -
     an absent section is correct; an empty one is a check finding. -->

## Notes

The registry package reaches its fixed point. All seventy-eight census rows now
reach their adjudicated terminal state, and the gate's exemption table is empty,
so the assertion runs against every row with nothing carved out.

Getting there corrected four adjudications that the evidence contradicted. Two
delete rows were wrong in opposite directions: the handoff-path family was not
dead and folded into its canonical owner, while the construct reader genuinely
was and went. The loader and snapshot rows were adjudicated for privatisation of
the whole module when only the implementation can go private, because their
construction entry points are contracts that test and tooling callers outside
the package depend on.

One row's reviewed owner was simply wrong: it named the loader as the definer of
a symbol the loader only re-exported. The split exposed it, and it now names the
module that defines it.

Proved the gate bites with the table empty: planting a borrowed export on a
keep-public module reds the terminal-state assertion by row id.