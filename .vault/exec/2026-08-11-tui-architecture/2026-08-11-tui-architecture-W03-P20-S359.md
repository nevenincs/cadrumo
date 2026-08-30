---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-30'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:c0f69112079f6d8f028be785758e3804d4f04d4d929169d779b50aa0e855c9dd'
step_id: 'S359'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Adjudicate the two unreachable members of the Workspace refusal union, and adopt a UNION-COMPLETENESS CHECK as the mechanism that found them. MEASURED, production constructions versus test constructions per member: ModeloWorkspaceVersionRefusalV1 0 production / 3 test; ModeloWorkspaceRevisionMismatchRefusalV1 0 production / 2 test; ModeloWorkspaceDomainRefusalV1 3 production / 1 test. The union advertises three refusal outcomes and the assembler can emit exactly ONE. WHY NOTHING CAUGHT IT: both dead members ARE constructed, in the workspace models test module and in the TUI workspace view-models test module. The tests build them by hand and assert on them, so they pass, and passing tests over a type read as evidence the type is live. A reachability defect hides most reliably behind green tests that construct their own subject. THE ADJUDICATION IS THREE-WAY, NOT PRODUCE-OR-DELETE, and must be made per member: (a) the check was intended and never written -- the finding is then the MISSING CHECK and the type is correct and waiting; (b) the refusal is genuinely unreachable by construction -- the type, its union membership, its validator, its view rendering and its tests all go together; (c) it is reachable and the assembler takes a different path today. The version refusal looks like (a): contract-version fields exist but are pinned to Literal[1], so a mismatch cannot currently be REPRESENTED let alone detected, which is a gap on a versioned contract rather than dead weight -- do not delete it on this evidence. The mismatch refusal needs the same question asked against the revision-assertion path first. DO NOT CLOSE EITHER BY FILLING recovery_action. THE GENERALISABLE CHECK, which is the durable half: for every closed union of outcome types, count PRODUCTION constructions per member; a member at zero is either an unwritten producer or a dead branch, and tests constructing it prove neither. It is mechanical, it reaches past this union, and it would have found both without anyone suspecting them -- which is exactly the property a hand-listed set lacks. NOTE FOR WHOEVER ACTIONS IT: view code already renders both dead refusals, tested against hand-built instances, so the deletion arm of (b) reaches into the TUI view layer and its tests, not only the model layer

## Scope

- `src/cadrumo/application/modelo/workspace_models.py`
- `workspace.py`
- `the two test modules that construct the dead members`
- `and the TUI workspace view modules that render them`

## Changes

- `A` `src/cadrumo/application/modelo/tests/test_workspace_refusal_union_reachability.py`
- `verify:` `pytest test_workspace_refusal_union_reachability.py` -> `2 passed`
- `verify:` `bite proof, dead member with no ruling` -> `FAILS as required`
- `verify:` `bite proof, ruling that outlived its member's deadness` -> `FAILS as required`
- `verify:` `production construction counts` -> `version 0, revision-mismatch 0, domain 3`

## Notes

BOTH DEAD MEMBERS ADJUDICATED AS CASE (a) -- the check was intended and never
written -- so neither type is deleted.

`ModeloWorkspaceVersionRefusalV1`: every `contract_version` field on the
Workspace models is pinned to `Literal[1]`, so a version mismatch cannot be
REPRESENTED, let alone detected. The type is waiting for the second version
that gives it something to refuse; deleting it would remove the only declared
handling for the first real bump.

`ModeloWorkspaceRevisionMismatchRefusalV1`: the row asked for the same question
to be put to the revision-assertion path, and the answer is measured.
`resolve_modelo_workspace_revision_axes` COMPUTES the mismatch -- it fills a
MISMATCHED disposition for the requested and stored sources against the
law-selected revision -- and its own docstring names this type as what the
assembly layer carries it into. The assembler never constructs it, AND no
production code reads either assertion's disposition: every consumer of
`requested_revision_assertion` and `stored_revision_assertion` is a test.
So a stored revision diverging from the law-selected one is computed, attached
to the resolved target as typed data, and read by nobody. The missing piece is
the emit, not the contract.

THE CHECK IS ASSERTED BOTH WAYS, which is what stops it decaying into
decoration. A member that becomes dead without a ruling fails; a ruling that
outlives the deadness it explains ALSO fails, so the record cannot silently
grow into an exemption list. Both directions were driven against the real
population from outside the repository, with no tracked file mutated.

The union's arms are READ from the alias, not restated: a literal copy would
agree with the union only until someone adds a member, and a member added to
the union but not to the copy is precisely the unreachable arm this gate
exists to notice.

The second test is the anti-tautology proof. Both dead members ARE constructed
in test modules and asserted on, which is why they read as live for so long, so
the counter must exclude the test tree or it measures the tests rather than the
system. It asserts the emitted member counts above zero AND that each
adjudicated member counts zero -- if the counter ever starts including tests,
every member reads as reachable and the first test passes while measuring
nothing.

NOTED, NOT ACTIONED: importing `workspace_models` as the FIRST import raises a
circular ImportError through `ledger.preflight` and `aggregation`. It does not
surface under pytest because another module imports earlier and breaks the
cycle, which makes it an import-ORDER fragility rather than a broken module.
