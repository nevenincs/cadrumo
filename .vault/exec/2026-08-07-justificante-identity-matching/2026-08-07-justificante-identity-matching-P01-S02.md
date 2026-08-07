---
tags:
  - '#exec'
  - '#justificante-identity-matching'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:d9f2a9749c4f4617c5a5d0eec5cbd568c22818fa9a0cccdfb33839137217f612'
step_id: 'S02'
related:
  - "[[2026-08-07-justificante-identity-matching-plan]]"
---

# Drop the now-signature-invalid expediente_id argument now that register_capture_justificante_metadata's existing csv equality check already covers identity

## Scope

- `src/cadrumo/application/live/_justificante.py (_justificante_matches_capture_axis)`

## Description

`register_capture_justificante_metadata` - the actual caller of
`_justificante_matches_capture_axis` - already asserts that the parsed receipt's
CSV equals the snapshot's, and raises, before the predicate runs.

## Outcome

Dropped `presentation_id=snapshot.expediente_id` from the call into
`matches_filing_target`. Strictly subtractive: it removed a comparison that could
never validly run, standing next to one that already does the real job, which is
unchanged.

## Verification

`test_justificante_capture_stamp.py` and the live suites stay green.

## Notes

The guard this site relies on was not touched, so the site's effective strength is
unchanged rather than reduced.
