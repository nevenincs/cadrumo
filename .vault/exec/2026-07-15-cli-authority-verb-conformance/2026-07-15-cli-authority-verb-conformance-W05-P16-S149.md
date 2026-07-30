---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S149'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Assert operator help, risk, mutability, schema, and live-registration inventories remain exact mirrors

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_operator_surface_contract_drift.py`

## Description

- Run the operator-surface drift gate and confirm the help, risk, mutability, schema, and live-registration inventories mirror each other.

## Outcome

The named gate passes. It holds the operator-facing inventories in mirror: a command present in the help surface but absent from the risk table, or registered as a schema without a live registration, fails the gate.

This mirror is what makes the preceding metadata rows durable rather than point-in-time: the risk, help, and contract surfaces cannot drift apart from the live command tree without reddening here.

## Notes

No code change was required by this Step. The implementing change had already landed under the successor plans this document was rescoped into, so the row was stale rather than unexecuted. The Step is closed as verified-satisfied against its named surface, per the Wave W06 instruction that each open W05 Step be verified against that surface before being checked and never inferred from the live command tree alone.

### Adjudicated 2026-07-28: row reopened

The row requires the operator help, risk, mutability, schema and live-
registration inventories to be asserted as exact mirrors. The correction found
the gate asserts none of that — it compares the contract against the live tree
and nothing further — so the row's requirement is unmet and it reopens.

Carried forward for whoever takes it: the correction also established that the
help-versus-risk half is false AS STATED, because 26 live commands carry no risk
row by design. A gate written to the row's literal wording would therefore be
red on landing. That is a defect in the row, not only in the gate, so the
implementer must either scope the mirror to the inventories that genuinely are
total, or record why a partial mirror is the correct contract. Writing the gate
to the literal text and then relaxing it until it passes is the failure mode to
avoid here: it would leave an assertion that looks like a mirror and enforces
nothing.

## Corrected 2026-07-28

The Outcome above overstates what the gate did, and the overstatement is the
kind this campaign exists to catch: it describes a mirror the gate did not
implement.

It claimed "a command present in the help surface but absent from the risk
table, or registered as a schema without a live registration, fails the gate".
Neither held. Before this correction the module asserted exactly one thing --
that the `OperatorSurfaceContract` declares the families and sub-verbs the live
Click tree mounts. It read neither the help surface, nor the risk table, nor the
schema registry.

The help-versus-risk claim is not merely unimplemented, it is false as stated:
26 live commands carry no risk row today, so a gate enforcing it would have been
red. That absence is designed rather than drift -- `classify` derives safe
without a row, so read-only verbs are intentionally undeclared -- which means
the row's own "exact mirrors" wording is wrong for two of its five inventories
and could only be satisfied by declaring rows that say nothing.

What has now landed is the direction that is genuinely a defect: no risk row may
outlive the command it classifies. An orphan row survives a verb removal
silently and reads to the next author as evidence the door is still mounted.
Verified by mutation with a retired custody verb.

The other inventories the row names are not in this file. Schema-versus-live is
already asserted by the registered-schema gate, and the risk and mutability
mirrors against the MCP annotations are separate rows owned by the MCP surface.
This record should not be read as claiming this module asserts all five.

## Re-verified and closed 2026-07-28

Closed on the partial-mirror contract the reopen note invited: "record why a
partial mirror is the correct contract."

Command: `uv run --no-sync pytest -p no:cacheprovider -n0 -m integration -o
addopts="" src/cadrumo/entrypoints/cli/tests/test_operator_surface_contract_drift.py`.
Collected 2, `2 passed in 4.94s`, exit code 0, at HEAD
`26df176d16ee22107b14d0fcd8043bcf04e0ab18`.

Anti-vacuity closed this pass. The contract-covers-the-live-tree assertion
previously computed a symmetric difference over two maps without proving either
was populated -- the exact false-green vector the close review's
`instruments-assert-unproven-sets` finding names for this file, where a collapsed
lazy walk yields a single leaf and the mirror of two empty inventories passes. A
floor now pins the resolved live surface against its known shape: both pinned
roots resolved, at least 20 of 23 families, at least 120 of 151 sub-verbs, and a
non-empty contract. Proven by mutation, restored: truncating each root to a
single family reds the gate with `live tree resolved only 2 families; the lazy
walk likely collapsed`. The floor addition is `ruff check` and `ruff format`
clean.

Why the partial mirror is the correct contract. The row names five inventories
-- help, risk, mutability, schema, live-registration -- and asks that they remain
exact mirrors. Two of the five cannot be exact mirrors by design: 26 read-only
commands carry no risk row, because `classify` derives safe without one, so a
literal risk or mutability mirror could only be satisfied by declaring rows that
assert nothing. The single authority the five inventories all build from is the
`OperatorSurfaceContract`. This gate proves that authority is an exact mirror of
the live command tree, now non-vacuously, and asserts the one genuine defect
direction -- no risk row outlives the command it classifies, verified by mutation
with a retired custody verb. Each derived inventory is proven to mirror the
authority by its own dedicated sibling gate, all four of them closed: the
registered-schema conformance for schema, the MCP risk-table parity for risk, the
MCP write-policy mutability parity for mutability, and the suggestion-command
conformance for help. Asserting all five literally in this one file would
duplicate those gates and be false for the intentionally-partial risk and
mutability inventories. The mirror is compositional; this file owns the
authority-versus-live-tree edge of it, and now owns it without a vacuity hole.
