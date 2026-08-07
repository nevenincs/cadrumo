# AEAT quality gates

Write real-behavior tests. Do not use fakes, mocks, stubs, monkeypatches, skipped
tests, xfail markers, or tautological assertions to make gates pass.

For calculation tests, derive expected values from AEAT workbooks, BOE or AEAT
examples, registry-authoritative fixtures, or live oracle replay. Do not
hand-compute the same formula the registry declares. Test structure, graph
wiring, validation errors and provenance when no external numeric oracle exists;
do not assert arbitrary `Decimal` outputs produced only by the test author.

Reject duplicated symbols, shadowed responsibilities, misplaced code, import
cycles, dead code, and cross-package private imports. Run structural audits at
milestone and cluster gates.

## A gate is unproven until it bites

Break the production code on purpose, confirm the gate reds, restore. Prefer a
runtime monkeypatch from **outside** the repo over an edit to a tracked file:
nothing under `src` changes, so a peer's sweep cannot commit the mutation and a
crashed run leaves no residue. The edit form is only unavoidable when the fix is
not yet in the code; announce before opening that window.

An anti-tautology proof over synthetic input is necessary but not sufficient — it
cannot catch a detector correct on synthetic input that never reaches the real
site.

**Allowlists are where the judgement moves**, so require every entry to state its
reason and make stale entries fail. Key exemptions by `(path, enclosing
function)`, never by line number. For any gate pinning registry ids, add a
fixture-anchor test asserting those ids still carry the property they are named
for, or a rename makes the module pass vacuously.

**Never hardcode an exact count as a pass condition.** Gate on the property, not
the tally: a module count or import-site ceiling encodes a moment, trains
everyone to update the constant, and then detects nothing.

**This repo's gates overlap**, so satisfying one can violate another. Verify a fix
against both before committing. The tell is oscillation — if fix A reds gate B
and fix B reds gate A, neither is right and a third shape is needed. Never
resolve it by hiding the construct from one gate's matcher.

## Retiring an enum member

Before deleting a retired enum member, reconcile every validation, schema,
fixture and test consumer into one coherent accept-or-reject state, and prove the
owning collection gate is green. A member can look retired at the CLI layer while
still powering a contradictory registry-validation surface — schema construction
accepting it, validation routing it positively, selector validation rejecting it.
If collection is red from peer work, leave the deletion open and record the
blocker.

Companions: `no-tautological-calculation-tests`, `aeat-roundtrip-discipline`,
`verification-grounding-needs-oracle-evidence`,
`full-tree-gate-must-distinguish-owner` (triaging a red tree-wide gate).
