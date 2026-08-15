---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:9b03118188fdbcdd54a91908c30a3b9ff5bf347aef68b63913baaf8457b4cfe7'
step_id: 'S39'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh delete the re-export bridge module in the custody package and repoint its sole consumer at the two modules it forwards to, in one commit

## Scope

- `src/cadrumo/adapters/persistence/storage/custody/_label_head.py`

## Description

- Delete the standing re-export bridge and repoint its consumer at the two
  modules it forwarded to.
- Delete the orphaned test adapter export module found alongside it.

## Outcome

The bridge is gone and no importer of it remains anywhere in the tree. The
consumer now reaches the two modules directly, which is what the boundary rule
asks for: there are no standing non-facade re-export bridge modules, and the
canonical home is the owning module rather than a forwarding hop.

A second deletion rode with it for a different reason, and that reason is the
part worth keeping. A test adapter export module survived whose sole consumer --
a twelve-hundred-line test module -- had been deleted earlier the same day,
leaving the export it existed to serve behind with zero importers. That is not a
shim question but a deletion-completeness one, and it was invisible to the
existing detector because the re-export-bridge scan does not walk the test tree.

## Notes

This record is written after the fact. The work landed and was correct, but the
step was marked complete without a matching execution record, so the plan gate
reported it for some time as a checked step with no record.

That is the discipline this campaign relies on failing in its quietest
direction. A missing record does not make the work wrong, but it makes
delivered-as-specified, delivered-narrower and recorded-but-not-implemented
indistinguishable at the checkbox -- and here it would have lost the more
valuable half of the step, which is the detector gap rather than the deletion.
The bridge deletion was the assignment; the observation that a whole class of
orphan is invisible because the scan skips the test tree was the finding, and
nothing outside the commit message carried it.
