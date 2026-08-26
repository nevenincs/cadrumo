---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:bdfd565d4272a758f89d16a8c9f93377360f831d1b61034e64e3728d156bd4f2'
step_id: 'S157'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Replace the direct CLI profile-logout execution door with the composed public operation API and delete its application-authority call path without a compatibility branch

## Scope

- `src/cadrumo/entrypoints/cli/_config/_custody.py and focused CLI operation-projection tests`

## Changes

M src/cadrumo/entrypoints/cli/_config/_custody.py
M src/cadrumo/entrypoints/cli/tests/test_profile_lifecycle_navigation.py
- `verify:` `pytest test_profile_lifecycle_navigation.py -m integration -n0` -> `9 passed, 2 pre-existing`

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

Logout now submits and starts the registered `user-profile.logout` operation
through the composed graph and settles it. The start door awaits the executor
to completion, so no observation or polling pass is needed to know the session
closed, and the already-logged-out case is exactly the no-active-pointer branch,
so no effect read is needed either. The direct call into the session-revocation
authority is gone from the CLI with no compatibility branch behind it.

The proof is the journal. A direct authority call closes the session and records
nothing, so asserting only that the pointer clears would pass against either
implementation; the test asserts an operation-platform record appears under the
storage root, which only the supervised path produces.

## Notes on a defect this Step introduced and closed

The first landing of this Step reached for the composition module four levels up
rather than three, which resolves to the package root instead of the entrypoints
package. Every `config logout` invocation then died at the terminal boundary
with a ModuleNotFoundError. It reached the tree because the work was swept into
a commit while an attribution check was in progress.

That attribution check was itself wrong, and the way it was wrong is worth
recording: restoring a file from HEAD does not isolate a change that HEAD
already carries. The revert restored the defect, the failure persisted, and the
persistence was misread as proof the failure pre-dated the change. Attribution
must compare against a revision known to precede the work, which is how the two
remaining failures in this suite were confirmed to pre-date it.
