---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:84adedcef181312528761b86b1cb7c2fb89fff67ac1cb31e130ba30285b712d9'
step_id: 'S241'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Privatize the snapshot implementation after eliminating every external consumer and public package reach

## Scope

- `src/cadrumo/domain/calculations/registry/snapshot.py`

## Changes

A src/cadrumo/domain/calculations/registry/_snapshot_internals.py
M src/cadrumo/domain/calculations/registry/snapshot.py
M 6 in-package consumers repointed onto the private implementation
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

Thirty-four construction, validation and cache symbols moved. snapshot.py keeps
build_snapshot and build_validated_snapshot, the two symbols callers outside the
package bind.

The row says privatise the IMPLEMENTATION, and that word settles what looked
like an open design question. The authority-owned rule governs production paths
and no production caller sits outside this package; the architecture rule says a
contract required outside its package -- counting test, fixture and tooling
consumers -- lives in a public defining module. So the contract stays public and
the machinery goes private.

The boundary was found by measuring, not by reading names. A first attempt kept
four symbols public and broke immediately: two of them are called BY the
internals and used only in-package.