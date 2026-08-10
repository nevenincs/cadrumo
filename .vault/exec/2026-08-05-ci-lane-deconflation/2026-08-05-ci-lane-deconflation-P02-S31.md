---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-05'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:afed6942cf421f18116672a0b0d198744bdf8e863a76ee1ac1fa2edacc689a5e'
step_id: 'S31'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---

# Enrol the unreachable dev/registry/tests modules

## Scope

- `justfile`
- `pyproject.toml`

## Description

- Check the markers in the directory before choosing between a path fix and a marker fix.
- Add the marker exclusion to the dev-tooling expression FIRST, then the path, then remove the three ignore directives, in that order.
- Measure the enrolled selection before landing, rather than after.

## Outcome

The directory is reachable, and the exclusion that remains states its own reason.

The fix is marker-based rather than path-based, and the check that produced that shape is the whole value of the row. `test_workbook_parity` is the only file in the directory carrying `external_tool`, while the dev-tooling expression excluded only `resident_service`. So the three ignore directives were inert ONLY because nothing collected the directory: enrol the path without amending the expression and the one in the shared options becomes the sole guard keeping a LibreOffice-dependent module out of the lane. Removing them as "inert fossils", which is what this row said before it was corrected, would have reddened every machine without LibreOffice.

Order therefore matters and is written into the change so the diff reads as the argument: marker exclusion first, beside the one already there, then the path, then the removal. Within one commit it is atomic and the ordering is moot, but a later reader splitting it would reintroduce the window.

Marker over path is the better shape rather than the safer one, and the reachability gate says why in its own third assertion: it asks whether a test no lane runs carries a marker stating the reason. A marker states one. A path ignore states nothing, which is how three of them accumulated across two files after they had stopped meaning anything.

## Notes

Measured before landing, not after: 138 passed, 0 failed, 24 deselected, exit 0. The 24 are exactly the cases the amended expression is designed to hold out.

Zero reds inverts what everyone expected, including me. The row was written anticipating rot across thirteen modules that had never executed, and the queue treated it as containment on the assumption a triage list would follow. There was nothing to triage, and that finding belongs to the sibling row.

The measurement gated the landing rather than following it. The change was built and left parked and uncommitted while the run was queued, because landing an enrolment whose blast radius nobody had measured is the specific failure this campaign exists to avoid. The arithmetic supported waiting: modules were arriving at roughly one every two hours, a measurement was minutes away, and the downside of a wrong landing was a red tree for six leads at once.

One thing the measurement does not settle. A file in the executed set is uncommitted peer work, so a clean checkout runs slightly fewer tests than 138. The result is not distorted by it, since that file passed, but the number is a working-tree number and this record does not present it as a checkout number.
