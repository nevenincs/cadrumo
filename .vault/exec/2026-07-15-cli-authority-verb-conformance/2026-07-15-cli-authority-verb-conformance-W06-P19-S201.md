---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S201'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Run the complete serial integration suite and record the attributable result

## Scope

- `src/cadrumo/`

## Description

Run the complete integration suite in both lanes, the bulk under workers and the
isolation-sensitive serial-marked tests alone, and record the attributable result of each.

## Outcome

FAILED in both lanes. No global green is claimed. One root cause dominates the parallel lane
and is uncommitted peer work.

Parallel lane. Command: `uv run --no-sync pytest -q -rf -n 6 --dist=loadfile -m "integration and
not serial and not os_keychain" --tb=line`. Exit line `125 failed, 3103 passed, 7 warnings, 19
errors in 1013.90s`, exit code 1.

Serial lane. Command: `uv run --no-sync pytest -q -rf -m "integration and serial and not perf and
not os_keychain" -n0 --tb=line`. Exit line `7 failed, 26 passed, 17682 deselected in 666.98s`,
exit code 1. The serial lane was run separately and with no workers, as required, because a
worker-parallel run silently holds these tests out while reporting a clean pass.

HEAD was `c293706ce3` at the start of the pair and `eb117d592e` at the end.

Dominant parallel-lane cause. 128 failing assertions and all 19 setup errors carry one identical
message: the MCP input-schema build could not resolve one command subtree, `operator_output`
followed by a test-probe segment, and refused rather than shipping an argument-free schema. That
key is registered by an UNTRACKED peer test module under the application operator-output package.
A test module is registering a production schema key for a command that does not exist. 95 of the
125 failures are in the MCP entrypoint package behind this one refusal; the same key is what makes
the CLI JSON schema conformance suite report a registry key with no matching CLI leaf.

Other parallel-lane failures. 12 in the CLI entrypoint package, including the sequence-contract
failure already recorded under S187. 12 in the agent evaluation package.

Serial-lane failures, all seven. One aggregation scale benchmark latency assertion, which is a
timing gate on a machine carrying 98 concurrent Python processes from other agents. One installed
MCP sibling-CLI resolution test, and five installed-oracle tests under the packaging tree. All six
of the latter require a built and installed release cohort, which does not exist in this
workspace.

## Notes

The refusal that dominates the parallel lane is the system behaving correctly. It is designed
to refuse rather than silently ship an argument-free schema, and it did. The defect is the peer
test module that registers a production registry key, and it is uncommitted, so the lane cannot be
measured cleanly until the working tree settles.

Custody cases carrying the OS keychain marker were excluded from both lanes. They fail with a
Windows error 1312 under an agent logon, have never been observed green in any lane, and remain
unverified.

The semantic code index was degraded throughout this Phase: the service reported `Source code sections: 466` against 3982 tracked Python files while declaring its code generation succeeded. No absence recorded here rests on a semantic miss.
