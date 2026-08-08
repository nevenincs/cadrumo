---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:9fd8f5c689f66223a775be1f8be21a8751549a7e0e58a7708e3c7bb84f584421'
step_id: 'S159'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# Make the column-role mapping request declare its evidence posture

## Scope

- `src/cadrumo/llm`

## Description

- Rule that a tabular file's header row is the file's schema and not taxpayer evidence, and record that ruling in the governing decision record as a new subsection.
- State the evidence marker explicitly at the column-role request builder, with the judgement written at the site rather than inherited from the model default.
- Add a gate walking the production AST for every request construction: it refuses any that omits the marker, refuses any constant-false declaration that is not enrolled with a reason, refuses a stale enrolment, and asserts the scan finds the five known builders so it cannot pass over nothing.
- Anchor the single enrolment on the structural fact holding it up: the prompt compiler accepts headers and nothing else, and the instruction it writes forbids the model to reproduce data.

## Outcome

The ruling is the second option, not the first: the request stays unmarked in VALUE but is no longer unmarked in FORM. Marking it would have put a schema-shaped payload behind a taxpayer-evidence consent token and closed the gated hosted lane the tabular measurement runs through, buying no confidentiality. The real defect was that the judgement lived in a missing keyword argument, so a builder that judged and a builder that forgot were byte-identical in source.

The residual is recorded rather than argued away: a bank export header can carry an account fragment or a holder name, and the parameter would accept a row of values as readily as a header row. The header-only property is now held at the prompt compiler's signature, which the gate treats as a tripwire.

A sixth builder is now a decision someone took. Five production builders exist; four mark their content, and the fifth is enrolled with a stated reason.

## Verification

    uv run --no-sync pytest src/cadrumo/llm/tests/test_evidence_marker_declared_at_every_builder.py -n0 -q -m unit
    4 passed in 10.03s

Run in the wider gate selection alongside the consent surfaces:

    uv run --no-sync pytest <five consent and mapping gates> -n0 -q -m unit
    69 passed in 41.92s

The complementary lane selects nothing on these paths and is stated rather than reported as a second green: 17 deselected under the not-unit marker expression.

Mutation-proven from an out-of-repo pytest plugin at module scope, loaded with `-p` and asserted to have printed its banner. The plugin patches the read path for the single production file the gate scans, so no tracked file was edited:

    MUTATION=none  4 passed in 10.03s   (control, banner printed)
    MUTATION=s159  2 failed, 2 passed

Stripping the marker reds both the posture assertion and the enrolment assertion, and leaves the scan-non-vacuity and prompt-signature anchors green -- the two that should not move.

## Notes

No live inference was triggered; both gates are model-free and read source rather than dispatching.

The decision-record amendment is written to the governing record but is not yet in a commit: that file also carries an unrelated in-flight amendment from a concurrent lane, and the document's body hash covers the whole body, so committing only part of it would record a hash that does not match the committed text. It is left for the sweep that lands vault work coherently.
