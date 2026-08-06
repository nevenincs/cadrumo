---
tags:
  - '#exec'
  - '#ledger-invoice-decomposition'
date: '2026-08-06'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:7de8052927eaed7941ed239992a0fbe0fb0e92d62c458ec32c93234973bd9777'
step_id: 'S35'
related:
  - "[[2026-08-05-ledger-invoice-decomposition-plan]]"
---

# Restore the marker integrity the two campaign-owned test modules broke, so the marker gate stops reporting a campaign surface as unclassified

## Scope

- `src/cadrumo/domain/iva/tests/test_component_expectations.py`

## Description

- Raise `pytestmark` above the first statement in the modules that had declared it late, so the marker gate classifies them.

## Outcome

Landed as commit `f6be4c603d`, "test: raise pytestmark above the first statement in four modules".

RECONSTRUCTED RECORD, written 2026-08-06 from the commit rather than contemporaneously, under the plan-closure rule.

The defect was positional, not a missing marker. `pytestmark` declared after the first statement is invisible to the gate that partitions the suite into marker lanes, so a module carrying the correct markers still reported as unclassified. Four modules were corrected, of which this campaign owned two.

Why it matters beyond tidiness: an unclassified module is not merely mislabelled, it is DESELECTED by the marker expression the lanes run under. The repository prints a NOTHING RAN banner precisely because a selection that matches nothing exits zero and reads as green. A campaign surface silently outside both lanes is a suite that passes without executing the tests the campaign added.

## Verification

```
uv run --no-sync pytest src/cadrumo/domain/iva -n 0 -q --no-header
```

Re-verifiable directly: the module's `pytestmark` now precedes its first statement, and the module is selected rather than deselected under the unit lane.

## Notes

Reconstructed after `vault plan status` reported this Step checked with no execution record. The commit was located by SCOPE FILE, never by step id: a bare `git log --grep=S##` returns commits from other campaigns, because step ids are per-plan and collide across plans. That search produced confident and entirely wrong matches for all nine unrecorded steps before the namespace error was caught.

Five remain unreconstructed: S25, S29, S30, S31 and S32. Their commits were not identifiable from the scope-file history in this pass, and no record was written for them rather than one asserting verification nobody performed.
