---
tags:
  - '#exec'
  - '#test-harness-honesty'
date: '2026-07-26'
modified: '2026-07-26'
body_hash: 'sha256:77d42545cfc283d6ae981351bf68a10c5238113aa1980fee2862e2229b98ff23'
step_id: 'S12'
related:
  - "[[2026-07-25-test-harness-honesty-plan]]"
---

# Audit the gate surface for checks reachable only through a marker-scoped or narrowed selection

## Scope

- `src/cadrumo/tests/`
- `dev/`
- `justfile`

## Description

- Read `testpaths` and confirm it names only `src/cadrumo` plus one packaging file.
- Extract the real pytest invocations from every justfile recipe and every CI workflow.
- Inventory every test directory under `dev/` and diff it against what any lane names.
- Execute the ten unnamed directories to measure whether they pass.
- Add `just test-dev-tooling` naming all ten with an explicit marker expression.
- Add a live-recomputed coverage gate under `src/cadrumo/tests/`, marked `unit`.
- Prove the gate bites by removing one directory from the recipe and observing the refusal.

## Outcome

The step's hypothesis was that a gate's slowest half goes unrun. The measurement
found something broader: ten whole test directories under `dev/` are named by no
lane, no workflow, and no `testpaths` entry, so 569 tests had never executed and
no one had ever seen their result.

Nineteen of them were failing. The duplication-disposition gate this step cites
as its motivating example was one; the others were the Terminology Handbook
conformance gates and the gates over the shipped documentation-search corpus.
The step's framing was therefore right about the consequence and wrong about the
mechanism, which matters because the remedy differs: a narrowed marker needs its
expression widened, an unnamed directory needs a lane to exist at all.

Coverage now has a lane and a guard. The guard recomputes both sides on every
run and fails with the orphaned directories named, so a directory added later
that no lane names refuses immediately rather than joining an invisible set.

## Notes

The guard is deliberately placed in `src/cadrumo/tests/` and marked `unit`.
`dev/tests/` is itself one of the ten orphans, so a guard against unreachable
directories placed there would have been unreachable by the exact defect it
exists to catch. This mirrors the reasoning already recorded in the packaging
preflight selection gate, which marks itself `unit` for the same class of
reason.

Verified by regression rather than by reading. Removing one directory from the
recipe reds the guard naming that directory and both its files; the justfile was
restored from a copy taken beforehand, with no destructive git operation
involved.

One limit is left open deliberately and is stated in the gate's own docstring
rather than only here: a justfile recipe satisfies the guard, and a justfile
recipe is not CI. Requiring a workflow step is the stronger invariant, and it is
not enforced yet because the new lane is still red on the failures inherited
from the unobserved period. Enforcing it now would place a knowingly-red lane in
the shared pipeline and tax every peer for a problem they did not create. That
tightening is the remaining half of this step's intent, and the docstring says
to delete its caveat paragraph when the lane goes green.

Semantic code discovery was unusable throughout. The index held roughly 188
sections against roughly 4546 source files while reporting itself available with
an empty degraded-reasons list, so every claim here rests on direct reads,
`rg`, and executed measurement.
