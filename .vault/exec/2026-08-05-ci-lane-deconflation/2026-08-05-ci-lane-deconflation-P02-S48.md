---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:db0415c2bfc7afe1dbeed075035f13c2037f67fc9b2c3d6f344924a54864337d'
step_id: 'S48'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---

# Repair the workflow-conformance gate that S31 left pinning a removed ignore directive, because S31 correctly deleted the three redundant --ignore directives from the test-unit recipe once the marker expression carried not external_tool, but test_ci_workflow.py still asserts that the recipe body contains --ignore=dev/registry/tests/test_workbook_parity.py, so the gate has been red since that landing and reds for every agent who runs the dev-ci lane, and this is S31's collateral rather than a new defect, noting that the fix is to re-pin the gate on the property S31 established (that the workbook-parity module is held out by its external_tool marker rather than by a path ignore) rather than to restore the directive, because restoring it would undo S31 to make its own gate pass, and noting that the gate's other three assertions on the recipe body are still correct and must survive the repair

## Scope

- `dev/ci/tests/test_ci_workflow.py and justfile`

## Description

- Confirm the cause rather than the symptom: the recipe body no longer carries
  the ignore directive, so the gate's line search matches nothing and fails on
  its own lookup before reaching any assertion about the lane.
- Confirm the deletion was correct: the module carries `external_tool` at
  module level and the recipe's marker expression already excludes it, so the
  path ignore was genuinely redundant.
- Widen the body lookup to the recipe's unique marker rather than to a
  directive that is allowed to come and go.
- Replace the ignore-directive assertion with one on the property S31
  established -- that the tool-dependent module carries the marker the lane
  excludes.
- Prove the replacement bites by pointing the gate at a module stripped of the
  marker.

## Outcome

Landed as `90c74c685b36e6f1bf3040d81239cbb53a691816` (21 added, 6 removed).
The module is 33 passed and lint-clean.

The repair direction is the whole content of this row. The obvious fix was to
restore the deleted directive, and it would have turned the gate green in one
line -- by undoing S31 so that S31's own gate would pass. A gate is not
evidence that its subject should be unchanged; here the subject had improved
and the gate had not been told.

The replacement is strictly stronger than what it replaces, which is the test
of whether a repair was a repair. The old assertion could only observe that
one particular exclusion mechanism was spelled a particular way. It could not
notice `external_tool` being dropped from the module, which would silently
pull a tool-dependent test into the offline unit lane -- the actual failure
the exclusion exists to prevent. The new assertion sees exactly that, and the
mechanism is now free to change without a false red.

This is the fixture-anchor shape the quality-gates rule already names: a gate
that pins an identifier must assert the identifier still carries the property
it is named for, or a rename makes the gate pass vacuously. The same reasoning
covers a gate pinning a mechanism.

## Notes

Found while triaging the dev-tooling lane for an unrelated row, not by anything
that watches for it, which is the point S34 and S35 both make. The gate went
red at S31's landing and stayed red; nothing surfaced it, because the lane that
reaches it is invoked only by the dispatch-only full workflow and by a local
recipe nobody had reason to run. The red was found the same way S34 records the
last one being found -- a hand run undertaken for a different reason.

The row was opened rather than absorbed silently into the row being worked, so
that S31's close carries its own collateral rather than having it disappear
into a neighbour's record. S31 remains correctly closed: its change was right
and its verification gate was green for the property it asserted. What it did
not do was sweep the surfaces that pinned the mechanism it removed, which is
the same class as the verb-rename sweep the CLI contract rule already warns
about.

Five unrelated gates in `dev/ci/tests` and `dev/quality/tests` remain red and
are NOT this row's: an unwatched off-lane job in `ci-runner-probe.yml`,
nineteen packaging workflows using Actions artifact storage, operator-
identifying tokens in committed vault text, and an exec-outcome baseline
overrun of 2166 against 1879. Each belongs to an active peer campaign.
