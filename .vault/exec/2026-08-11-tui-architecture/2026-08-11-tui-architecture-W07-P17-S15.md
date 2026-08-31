---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:663f66d3011bfe5c029b68fee31f3e6be326cd2820eb4398d1218dfb6f85e19a'
step_id: 'S15'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Complete the derived live-tree fixed-point census joining every registered operation definition, recovery action, TUI, CLI and MCP exposure, executor factory, direct mutation or outbound site, and declared exclusion

## Scope

- `src/cadrumo/application/operations/tests/test_operation_catalogue.py`

## Changes

- `A` `src/cadrumo/application/operations/tests/test_operation_catalogue.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/application/operations/tests/test_operation_catalogue.py -m unit -n0` -> `fail`

## Notes

The red is the finding. Eight of the nine joins pass; the ninth reports that
29 projection claims reach no surface in the tracked tree, and that is an
accurate statement about the tree rather than a failure of the census. It is
landed red deliberately: reconciling the claims to make it green would remove
the evidence of the gap without making any operation more reachable. The three
reconciliation tasks are tracked separately.

Denominator, stated: 1939 tracked production sources and 20 registered
operations. The file list comes from `git ls-files` run as a subprocess, with
test packages filtered out, never from a filesystem walk, because an untracked
or in-flight file is not part of the tree anyone else sees. The operation set
comes from the single production composition seam called with no arguments. A
separate assertion requires the denominator to reach the operations package
and both frontend packages, so no join can pass by scanning nothing. No count
is a pass condition anywhere; the two figures appear only inside a failure
message.

Of the 29 unreachable claims, 10 name a projection tier that has no package in
the tree at all. The six auth operations reach no surface on any tier. Across
the whole frontend tier only three sites construct an operation request,
against 20 registered operations.

The detector was hardened before its result was believed. The first reading
reported 44; frontends call the application's own request builders rather than
spelling operation ids, so resolving one hop through those builders removed 15
false positives, all of which then joined a real surface correctly. The
remaining 29 were confirmed by hand.

One further finding is recorded but deliberately not encoded: a command-line
surface composes an export service and executes it directly, bypassing the
supervisor for an operation that has a registered definition, so that path
runs with no journal, no lease, no cancellation and no resumability. Any gate
here must judge whether a registered definition exists for the work being
done, not what the call is spelled; a matcher on the call name would police a
name rather than a shape. It is tracked separately.

Two `asyncio.run` sites are declared exclusions, each stating its reason, and a
separate assertion re-verifies each against the live tree so a stale exclusion
fails rather than silently widening the census.

Gate proven by mutation: dropping one definition from the production registry
reds the declared-against-registered bijection, and giving two definitions the
same recovery-action reference reds the action fan-out assertion. Both applied
as runtime patches from outside the repository.

Discovery for this Step ran against the local fallback index rather than the
live semantic-search service, which was down.
