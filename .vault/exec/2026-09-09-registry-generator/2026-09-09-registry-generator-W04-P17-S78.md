---
tags:
  - '#exec'
  - '#registry-generator'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:61cf8f37ce7dfd6373ba096b95381357b68d69124e50b3983ce9475edf0902a1'
step_id: 'S78'
related:
  - "[[2026-09-09-registry-generator-plan]]"
---

# Add the converse invariant to the offline check once the authority set is total: every manifest artefact resolves to exactly one declared authority, either a required entry or an off-host declaration

## Scope

- `dev/corpus/sync_aeat_record_design_corpus.py`

## Changes

- `M` `dev/corpus/sync_aeat_record_design_corpus.py`
- `verify:` `uv run --no-sync python dev/corpus/sync_aeat_record_design_corpus.py` -> `pass`

## Notes

The authority join alone proved insufficient and the invariant was widened during the Step.
An extraction sidecar carries the URL of the payload it was extracted from, so it resolves to
a declared required row and passes. The invariant therefore also requires the stored
extension to match the extension the declared URL serves, which is what separates an artefact
from a derivative wearing its source's URL. The planted-defect test in S79 is what surfaced
this; the first implementation would have passed a corpus containing a third sidecar.
