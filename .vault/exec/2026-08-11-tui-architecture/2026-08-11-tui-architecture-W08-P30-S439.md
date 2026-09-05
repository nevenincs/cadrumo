---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-05'
modified: '2026-09-05'
body_schema: 'body-v2'
body_hash: 'sha256:31d8be36080f0f3b9f4d39296e8be7f7a0f5493d06e30421788693367d3bc853'
step_id: 'S439'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Make the page-resolved cohort compiler read a wrapped record-design row whole. A design cell long enough to wrap is read line by line as fragments: the tail still ends in the casilla number so it parses as a valid cell beginning mid-sentence, and one row looks like a number occurring several times. Both failures are silent and point opposite ways, one writing a truncated label and the other refusing a casilla that is well determined. Reassemble rows before matching, and gate the property on a casilla outside the cohort.

## Scope

- `dev/registry/analysis/m200_2024_page_resolved_adjudications.py`
- `dev/registry/tests/test_m200_2024_page_resolved_adjudications.py`

## Changes

The parser defect S437 and S438 kept running into was still live in the cohort
compiler this Step's predecessor shipped. It compiled 40 of 40 members
correctly, which is exactly why it needed fixing: no member happens to wrap
today, so the compiler was right by luck rather than by construction, and the
next member with a long cell would have been resolved wrongly with nothing
saying so.

A design cell that wraps is read as fragments. The tail fragment still ends in
the casilla number, so it parses as a perfectly good cell that begins
mid-sentence, and the fragments of one row look like the number occurring
several times. The two failures point opposite ways and both are silent: one
writes a label starting "del Club Natacio Barcelona", the other refuses a
casilla for ambiguity the design does not have. That second shape is what put
DP200014B:00599 on the blocked list for two Steps.

Rows are now reassembled before matching, recognised by their leading
index/offset/width columns. The 40 members compile to byte-identical digests
afterwards, which is the evidence that the fix is behaviour-preserving rather
than a re-derivation.

The gate probes casilla 01264, which is NOT a member of this cohort. That is
deliberate: a parser asserted only through the current membership is asserted on
whatever that membership happens to exercise, and today it exercises no wrapped
cell at all. 01264 wraps, so it tests the parser on its own terms.

Teeth: the row-joining branch replaced by the old per-line harvest. The gate
failed with the exact fragment it names -- "del Club Natacio Barcelona (CNB) -
Deduccion pendiente/generada [01264]". Restored by copy, defect count 0,
5 passed.

## Notes

No label changed. Unlabelled casillas remain 4, unchanged from S438, and all
four still need a registry decision rather than locale work.
