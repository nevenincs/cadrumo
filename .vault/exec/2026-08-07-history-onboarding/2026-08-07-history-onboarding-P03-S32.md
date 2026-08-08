---
tags:
  - '#exec'
  - '#history-onboarding'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:89b645fda9d126ff817404dfbdfa716d7adf6e6c7d7a2a31ccd8e20a48b82405'
step_id: 'S32'
related:
  - "[[2026-08-07-history-onboarding-plan]]"
---




# relay the justificante unreached-evidence reasons onto the same envelope notices channel this plan's own advisories use, absorbing the sibling justificante-identity plan's deliberately-unlanded forwarding row rather than growing a second advisory channel, declaring the evidence_notices field on BulkFiledDataCaptureReport that the sweep was already passing and whose absence made the orchestration read raise AttributeError on a session-only path, verified by a test driving the full reason enum and asserting one notice per member with its reason readable in context, with the expected set derived from the enum rather than hand-listed

## Scope

- `src/cadrumo/application/live/_remote_state_models.py`
- `src/cadrumo/application/live/_filed_data_capture.py`
- `src/cadrumo/entrypoints/cli/_app_live.py`

## Description

- Collect the justificante enrolment notices the capture accumulator was discarding.
- Declare `evidence_notices` on `BulkFiledDataCaptureReport` and populate it from the sweep.
- Carry them on the run and forward them onto the one envelope notices channel.
- Add the full-enum relay tests and the mutation proof.

## Outcome

Three advisory sources now share ONE channel: this plan's expected-but-not-found
warning, its found-more-than-expected information, and the justificante
enrolment's per-artefact unreached-evidence reasons. The sibling plan stopped
short of forwarding its reasons precisely because doing so needed this surface,
and putting notices on a CLI result payload is what the CLI contract forbids; a
second channel would have been the duplicate-advisory defect.

The reasons are forwarded VERBATIM, one notice per artefact, each keeping its own
reason in context. Six distinct dead ends previously shared one shape -- a log
line and a `None` -- so a capture could extract casillas and report zero
justificante evidence with no visible cause. Collapsing them into a single
"evidence not enrolled" notice would rebuild exactly that silence one layer up,
which is why the relay merges nothing.

A real defect surfaced while wiring it. The sweep was already passing
`evidence_notices` to `BulkFiledDataCaptureReport`, but the field was never
declared. The model does not forbid extras, so the keyword was silently accepted
and DROPPED, and the orchestration reading it back raised `AttributeError` -- on a
path that needs an authenticated session, so no test reached it. Proved by
extracting HEAD clean and reading the attribute: `AttributeError`. Declaring the
field closes it.

## Verification

    uv run --no-sync pytest src/cadrumo/application/live/tests/test_filed_history_onboarding.py -q -n0
    22 passed in 3.72s

The relay test drives the FULL reason enum and derives its expected set from the
enum rather than a hand-listed tuple, because a hand-listed tuple is exactly how a
newly added reason goes unrelayed and unnoticed. It also asserts one notice per
member, so nothing was merged in transit.

Mutation proof, run from OUTSIDE the repo tree:

    REASONS in enum: 6 -> ['unreadable_artefact', 'manifest_mismatch', 'unparsable_pdf', 'csv_unresolvable', 'csv_mismatch', 'filing_target_mismatch']
    CONTROL faithful relay holds: True
    MUTATION relay-flattened-to-one-notice: PASS (test would red)
    MUTATION one-reason-dropped-from-relay: PASS (test would red)

Before the field was declared, at HEAD:

    field declared: False
    accepts evidence_notices: YES
    read back RAISES AttributeError -> 'BulkFiledDataCaptureReport' object has no attribute 'evidence_notices'

After, from a clean HEAD extraction:

    field declared: True
    read back at HEAD: ()

## Notes

The mutation harness carries a layer check, prompted by a sibling's finding that
its first mutation patched a production enum and went green because the test binds
the enum at import time. Re-binding the production symbol here likewise leaves the
assertion unchanged, and the harness reports that explicitly rather than leaving a
reader to assume the aim was right:

    LAYER CHECK production-enum-rebound: assertion unchanged (module-level REASONS binding is what it reads)

So the mutations aim at the relayed data, which is what the assertion actually
reads. A mutation aimed at the wrong layer produces a green that proves nothing.

The `evidence_notices` field is additive and defaulted, so every existing caller of
the bulk report is unchanged and `capture_filed_data_bulk`'s own contract is
untouched. It rides an application-layer report rather than a registered CLI
payload, which is where the envelope-notice prohibition applies.
