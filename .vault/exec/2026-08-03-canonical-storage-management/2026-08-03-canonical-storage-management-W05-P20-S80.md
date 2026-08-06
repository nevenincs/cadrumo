---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:b1c303f795be7c0b51e6c2cb57352928330ab6d6423bf44c969dca826ff2c465'
step_id: 'S80'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Extend or document the provenance gate's join-detector blind spot, under which a local rebind such as assigning the root to a variable before joining evades the direct-attribute match and is not flagged, before the pending-enrollment table is treated as a complete inventory

## Scope

- `src/cadrumo/tests/test_storage_provenance_gate.py`

## Description

- Extend the provenance gate's join-detector to track local rebinds of the storage root, so a local variable assigned the root and then joined is treated as a join rather than evading the direct-attribute match.

## Outcome

Landed in commit `048f2491dc` ("follow the storage root through a rebind, and bind each gate to a real subject"), committed at HEAD. The detector now follows the root through a function-local binding: a name assigned the root, then joined, counts as a join. Scope is deliberately bounded to the function plus its enclosing scopes and no further — chasing the root through parameters and returns is named in the gate's own docstring as where a heuristic starts flagging healthy code. Gated by `test_the_detector_follows_the_root_through_a_local_rebind`, `test_the_detector_follows_a_rebind_into_a_closure`, and a negative control `test_the_rebind_tracking_does_not_flag_an_unrelated_local`. Closing this blind spot surfaced a real five-join site that had been evading the detector — the table's own docstring records this as the one direction a pending-debt count may legitimately grow (an honest larger number replacing a flattering smaller one), and that site was then migrated and struck by the ordinary route.

## Notes

This landed between the Step being authored and this record being written — caught on a routine re-verification pass rather than assumed still-open from the Step's own text. The plan's ADR audit (R9) already reflects the gate's current, rebind-aware scope.
