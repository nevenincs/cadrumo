---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:2e4d3155107fc017ba71b37c2cc964d0c96531a611f8e143ecc13b4f5d2de805'
step_id: 'S205'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# Thread the filer's identifier to the grounding entry point

## Scope

- `src/cadrumo`

## Description

- Thread the filer's own tax identifier from the bucket down to the grounding entry point, so the counterparty role resolution the entry point was built to perform is reached on the live reading path.
- Resolve the identifier at the reading path's own call site rather than requiring every caller to supply it, which is what let the sole production call site pass only the draft and the transcription.

## Outcome

Delivered as specified. The entry point accepts the filer's identifier and skips counterparty identity resolution entirely when it is absent, so before this the resolution never ran on the live path at all and its documented first-checksum-valid-identifier defect was guarded only in isolation.

The threading landed in commit 87709888c1, across the reading path and the filer-establishment module. **This record was written by a different agent than the one that implemented it**, after the row was found open with the code landed. The implementing lane declined to write it on the ground that attributing a peer's work to its own execution document would be dishonest, which is right, and the row is closed here against the evidence rather than against a claim of authorship.

## Verification

Cited rather than re-derived, because the strongest available demonstration already ships as a gate. The direction cross-check's live-path anchor stands up a real bucket carrying a real profile, a real document and a real transcription, drives the public entry point, and observes the derivation receiving the profile's identifier:

    uv run --no-sync pytest src/cadrumo/application/ledger/tests/test_direction_reaches_the_confirm_boundary.py -n0 -q -m integration
    5 passed in 17.10s

`test_the_profiles_identifier_reaches_the_derivation_on_the_live_path` is the one that settles this Step: it asserts the identifier arrives where the threading was supposed to deliver it, on the path that had been skipping it. Its module docstring states the gap directly -- each end was gated given a profile while the threading between them was gated only structurally, so the slot could have been written empty on every real document with the suite green.

The anchor was read at the committed tree before being cited, rather than recalled, and run in the integration lane; the default lane deselects all five, so a bare invocation of that path reports success while selecting nothing.

## Notes

The Step is recorded as delivered rather than delivered-narrower: the entry point receives the identifier on the live path, which is what the row asked for, and the dependent direction work reads the same identifier and is itself gated.

No new test was written for this record. Re-deriving proof that already ships as a live-path anchor would add a second authority on one question, and the campaign's own guidance is to cite the anchor rather than restate it.
