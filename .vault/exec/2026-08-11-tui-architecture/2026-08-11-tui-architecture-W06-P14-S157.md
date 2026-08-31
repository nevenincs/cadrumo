---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-27'
body_schema: 'body-v2'
body_hash: 'sha256:f6cdc6f9b144b96e0fa24bd425b55937b116f992baa1ba1e2617f2dda2abfa85'
step_id: 'S157'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Replace the direct CLI profile-logout execution door with the composed public operation API and delete its application-authority call path without a compatibility branch

## Scope

- `src/cadrumo/entrypoints/cli/_config/_custody.py and focused CLI operation-projection tests`

## Changes

M src/cadrumo/entrypoints/cli/_config/_custody.py
M src/cadrumo/entrypoints/cli/tests/test_profile_lifecycle_navigation.py
- `verify:` `pytest test_profile_lifecycle_navigation.py -m integration -n0` -> `9 passed, 2 pre-existing`

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
