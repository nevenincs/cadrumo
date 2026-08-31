---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:062472fd5c845f7b408e4d5081350ba8babf8dd136a63181eebcc64809e86656'
step_id: 'S325'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Thread the durable financial-operand custody repository through the production operation composition seam, which currently cannot construct at all: the supervisor refuses construction when any enrolled definition declares a transient financial operand and no custody repository was supplied, the modelo edit-apply definition declares one and is enrolled in the lifecycle definitions, and `financial_operand_custody` appears NOWHERE in either the application composition module or the entrypoints composition module -- the parameter was never added to either, so the wire does not merely go unpassed, it does not exist. Every production caller of that seam is consequently dead: the CLI censo pull path, the custody config verb, and the TUI launcher's operation services scope. Pass the custody repository through the application composition into the entrypoints composition so the supervisor's guard is satisfied by a real durable repository rather than by removing the declaration. Prove it by CONSTRUCTING the seam and submitting through it end to end -- an import-level test would pass against the broken state, because the failure is at construction and not at import; and prove the guard still refuses when a declaring definition is composed WITHOUT a custody repository, so the fix does not silently disable the protection it satisfies

## Scope

- `the operations application composition module`
- `the entrypoints operation composition module`
- `and a construction-and-submission proof through the real seam`

## Changes

- `M` `src/cadrumo/adapters/persistence/operations/financial_operand_custody.py`
- `M` `src/cadrumo/application/operations/composition.py`
- `M` `src/cadrumo/entrypoints/_operation_composition.py`
- `M` `src/cadrumo/entrypoints/tests/test_operation_composition.py`
- `M` `src/cadrumo/entrypoints/tests/test_registered_executor_conformance.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/entrypoints/tests/test_operation_composition.py -m integration -n0 -q` -> `pass`

## Notes

Discovery for this Step ran against the local fallback search index, not the live
semantic-search service, which was down for the session. Absence of a result in that
index is therefore not evidence that no such code exists; every claim about what does
or does not exist in the tree was confirmed by direct search of the source rather than
by the index alone.

THE FINDING IS NOT THE WIRE. Three tests already covered this break and were red at
the pre-fix commit: the production composition fixed point, the pre-login availability
case, and the actor-bound submission case, all in the entrypoints composition test
module. Confirmed by running them in a detached worktree at the pre-fix commit with
the resolved package path asserted first. So the gap was never missing coverage: the
integration lane carrying that coverage was not run when the enrolment that broke the
seam was accepted. No new test would have prevented this; running the lane would have.

The verify command above is scoped to the composition proofs and passes cleanly. The
wider entrypoints integration package does NOT reach zero: eighteen failures remain
there, all present at the pre-fix commit and none introduced here, confirmed by an
empty new-failure diff of the FAILED lists before and after. They are tracked
separately:
the registered-executor conformance matrix never enumerated the modelo family, and the
attestation authority shells out to a git subcommand that does not exist. Measured
effect of this Step on that lane: 27 failed and 9 passed before, 18 failed and 26
passed after, with occurrences of the custody refusal falling from 36 to 0.

The custody parameter is optional by design. Only a registry holding a definition that
declares transient financial operands needs it, and omitting it remains a refusal
rather than yielding a silently operand-less supervisor. The guard is satisfied by
supplying a real durable repository, never by removing the declaration or disabling
the check, and a proof composes the real production registry without a custody
repository and asserts it still raises.
