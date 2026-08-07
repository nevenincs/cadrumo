---
tags:
  - '#exec'
  - '#llm-package-split'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:59c649c880b168e1873ebe468d9c8e1ffcc79708174737858c3496ac5d33b4a1'
step_id: 'S12'
related:
  - "[[2026-08-06-llm-package-split-plan]]"
---
# Route read-time evidence resolution through DocumentShape and retire the read-time media-kind derivation

## Scope

- `src/cadrumo/application/ledger/_evidence_input.py`

## Description

- Declare the PDF-container shape set beside the existing structured and record-batch sets.
- Route the four read-time branches through it.
- Gate the retirement structurally, and bound the gate with the storage-side carve-out.

## Outcome

MediaKind is derived from the stored MIME type, and a label cannot see inside a
document. A ZUGFeRD invoice - a PDF carrying a complete machine-readable EN16931
record - answered PDF and was routed to prose extraction exactly like a
photograph of a receipt. The most exactly readable document in the corpus took
the least exact path, decided by a label.

DocumentShape is probed from the bytes themselves and never consults the MIME
type. The four read-time branches now ask it, through a hand-listed
PDF-container set rather than a name prefix, so a new PDF-carrying shape forces
a decision about whether page rasterisation is meaningful for it.

The two-member kind survives exactly where it belongs: mapping onto the
attachment manifest's taxonomy at write time, which is a storage classification
rather than a reading decision. The gate asserts that carve-out is still
occupied, so if the mapping is ever removed the exemption is deleted with it
instead of lingering as dead permission.

## Verification

The gate and its two bounding controls:

    uv run --no-sync pytest -q -p no:randomly -n 0 src/cadrumo/application/ledger/tests/test_read_time_shape_routing.py
    3 passed in 0.49s

The evidence surface, unchanged by the reroute:

    uv run --no-sync pytest -q -p no:randomly -n 4 src/cadrumo/application/ledger/tests -k 'evidence or draft or shape or textlayer'
    247 passed in 39.77s

Mutation proof - one branch restored to its media-kind form:

    1 failed, 2 deselected in 0.86s

## Notes

The gate is structural rather than behavioural because the failure it screens
for is silent: a caller re-deriving the routing from media_kind still produces
correct output for the two easy cases and mis-routes only the structured ones,
which reads as a slightly worse extraction rather than as a bug.

Its own first version carried the same blindness, matching only the attribute
spelling and missing the bare-parameter form. The bounding control failed and
surfaced it, which is what that control exists to do.
