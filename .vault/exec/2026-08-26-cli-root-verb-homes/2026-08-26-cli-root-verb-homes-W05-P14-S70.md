---
tags:
  - '#exec'
  - '#cli-root-verb-homes'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:34ca5c51258d1d43f990aed757c48adb9d5089b5ddcff026285d95d797585fdd'
step_id: 'S70'
related:
  - "[[2026-08-26-cli-root-verb-homes-plan]]"
---

# Correct S34's blocker: the tree went quiet and the capture still cannot run, because `capture_baseline.py` reads an attribute deliberately removed from LiveCommandNode three days ago

## Scope

- `dev/benchmarks/cli/`

## Changes

- `verify:` `python dev/benchmarks/cli/capture_baseline.py --samples 3 --warmups 1` -> `AttributeError: 'LiveCommandNode' object has no attribute 'execution_policy'`

## Notes

No code changed. This corrects what every previous record said about S34.

The tree went quiet for the first time in this campaign -- zero source writes in
three minutes -- so the documented precondition was met and the capture ran. It
failed in seconds, and not because of contention:
`_policy_payload` reads `node.execution_policy`, and `LiveCommandNode` has no
such attribute.

The removal was deliberate and is documented on the class itself: "Policy is
intentionally absent from this Click census. Executable policy authority is read
from the immutable CommandSpec graph by its consumers." It landed three days
ago. `capture_baseline.py` was itself edited twenty-three hours ago by a peer
aligning surfaces after a public rename, and `_policy_payload` was not swept
then either. So the tool has been unusable for three days with a peer having
been inside the file since.

**Every earlier record, including the third addendum, said S34 was blocked on an
uncontended tree.** That was incomplete: a perfectly quiet tree would never have
let it proceed. The contention was real but it was not the binding constraint,
and no amount of waiting would have revealed that -- only running it did.

The repair is not a one-line rename, which is why it is recorded rather than
done. `_policy_payload` needs `classification.capabilities`,
`classification.expanded_capabilities`, `write_route`, `destructive`, `handoff`
and `live_write`. The graph exposes `command_spec_for_path` and
`CommandExecutionPolicy` publicly through `command_api`, but the conversion that
builds one from a spec, `_execution_policy_from_spec`, is private to
`entrypoints/cli/__init__.py`. A consumer in `dev/` importing it would breach
the cross-package private-import rule. So the fix is one of two decisions, not a
repair: promote a spec-to-policy conversion onto the public `command_api`
surface, or drop `expanded_capabilities` from the census and read the spec's raw
policy fields -- which changes the schema of a provenance-stamped artifact.

Both belong to whoever owns the census contract. This campaign has declined to
sweep six `src/` modules broken the same way, on the principle that a
relocation's consumer sweep lands with its move; fixing this one because it
happens to block a campaign step would be the same inconsistency.
