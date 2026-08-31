---
tags:
  - '#exec'
  - '#tui-interface'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:4d534c0b59dedaa8a4adff389ee0069db463c126cb3725fc78eca15af3e89fc4'
step_id: 'S90'
related:
  - "[[2026-08-11-tui-interface-plan]]"
  - "[[2026-08-11-tui-interface-W06-P12b-S79]]"
---

# Prove zero unclassified action candidates through the retained action-denominator gate, plus an independent interaction and refresh proof for each of rename, discard, verify, file, export and amend asserting against the ENROLLED OperationDefinition rather than restating the action's semantics, then record the C4 exit governance fact as an execution record wiki-linking the C3 exit record. The denominator gate is reused, not rebuilt: the 2026-08-28 amendment retained it verbatim as a conformance test

## Scope

- `dev/quality/modelo_workspace_action_denominator.py`
- `src/cadrumo/application/modelo/operation_definitions.py`
- `and the per-action TUI interaction proofs`

## Changes

- `A` `.vault/exec/2026-08-11-tui-interface/2026-08-11-tui-interface-W06-P12c-S90.md`
- `verify:` `pytest test_modelo_workspace_action_denominator.py test_actions.py test_c4_action_accessibility.py test_create_deferred.py test_c4_{rename,discard,verify,file,export,amend}_action.py` -> `94 passed`

## Notes

THE C4 EXIT FACT. Zero unclassified action candidates through the retained
denominator gate, plus an independent proof suite for each of rename, discard,
verify, file, export and amend. Run 2026-08-31: 94 passed, 0 failed, HEAD
`2e19d04b73a4d450579f3e6bc90b99a47e5d3356`. AS WITH EVERY RECORD IN THIS CHAIN,
THE RUN WAS AGAINST THE WORKING TREE AT THAT HEAD RATHER THAN A CLEAN CHECKOUT
-- this worktree is shared and several lanes committed throughout the session.

THE DENOMINATOR GATE WAS REUSED, NOT REBUILT, as the row requires. The 2026-08-28
amendment retained `validate_modelo_workspace_action_denominator` verbatim;
W06.P12c.S81 added a second CANDIDATE STREAM to it rather than a second gate --
`discover_dispatchable_modelo_action_identities`, imported from the shipped
package so a new dispatch row enters the gate automatically.

EACH ACTION'S PROOF ASSERTS AGAINST THE ENROLLED DEFINITION rather than
restating the action's semantics, which is the distinction this row draws.
Capabilities, cancellation policies and baseline policies are READ from
`build_modelo_work_*_definition()`; none is copied into a test as a literal. So
a change to an operation's declared policy surfaces where the action is
enrolled, instead of passing because two copies of a constant still agree with
each other.

WHAT THE SIX PROOFS COVER, each pinning a different half of the platform's
contract rather than repeating one shape six times: whitespace STRIPPING for a
display name versus byte-exactness for an identifier and a path; cancellation
COOPERATIVE for verify versus UNSUPPORTED for discard and export; replay safety
(no taxpayer profile in a journalled verify request); the standing prohibition
on live AEAT submission, with a local filing proven never to count as official
evidence; journal confidentiality (exported bytes in neither request nor
result); and filed-record addressing for amendment, whose reason is mandatory
where discard's is optional.

THREE DEFECTS FOUND AND FIXED BY THESE PROOFS, all the same class and all
requiring different remedies -- a whitespace-only value accepted by
`Field(min_length=1)` on a display name, an identifier, and a destination path.
A blanket sweep would have been wrong: names are stripped to match the domain,
while identifiers and paths take a non-whitespace pattern and stay byte-exact,
because altering an identifier changes what it addresses and trimming a path
masks a typo. Each was journalled, leased and scheduled before failing at
execution -- real platform work for something that could never settle.

CARRIED FORWARD, NOT SILENTLY DROPPED: the action-specific accessibility matrix
named in W06.P12c.S89 is recorded on W06.P13.S93 instead, because all six
actions present through ONE shared OperationModal and six matrices would be six
copies of one surface's proof. That modal currently has no accessibility
coverage at all -- a measured gap, with its KDF-dependent runtime fragility
noted so the next attempt does not stand a 4x4x2 matrix on an unreliable base.

STANDING GOAL NOT COVERED: this record's predecessor relationship to the C3
exit record is a wiki-link, a human-checked claim. Nothing recomputes it, and
nothing fails if that predecessor later goes red.
