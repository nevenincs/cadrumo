---
tags:
  - '#exec'
  - '#llm-package-split'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:3c7b2e0003d2b67ccf9d8ca56b73126f1da818ce4c8bcbf104ab63b1be0b0199'
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
- Retire the read-time derivation itself: the `media_kind` field on the in-memory carrier, and the MIME-to-kind mapping that populated it.

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

The retirement clause landed in a second pass, on the scope file above, which
the first pass never touched. Rerouting the branches left the derivation itself
standing: the carrier still carried a `media_kind` field, and the resolver still
populated it from the manifest's MIME type on every read. No production caller
read it any longer, so it was dead weight in the reading direction - but it was
not inert, because the mapping that produced it also decided ADMISSION. It
refused anything whose declared type was not PDF, XML or `image/*`, which is the
same blindness in the one direction the branch reroute did not reach.

Admission now asks the probe. `DocumentShape.UNKNOWN` is its own
"never guessed at, always refused" verdict, so refusing on it moves the
authority to the bytes while every case where the label told the truth is
decided exactly as before. Only the two disagreement directions change, and both
change toward the document: a genuine invoice PDF announced as
`application/octet-stream` is admitted rather than rejected, and bytes matching
no readable shape are refused however respectable their declared type. The
`mime_type` field stays, unnormalised, as provenance and as the concrete type
the vision reader needs - carried, never consulted.

## Verification

The gate and its two bounding controls:

    uv run --no-sync pytest -q -p no:randomly -n 0 src/cadrumo/application/ledger/tests/test_read_time_shape_routing.py
    3 passed in 0.49s

The evidence surface, unchanged by the reroute:

    uv run --no-sync pytest -q -p no:randomly -n 4 src/cadrumo/application/ledger/tests -k 'evidence or draft or shape or textlayer'
    247 passed in 39.77s

Mutation proof - one branch restored to its media-kind form:

    1 failed, 2 deselected in 0.86s

The retirement pass, across every suite that constructs the in-memory carrier:

    uv run --no-sync pytest -q -p no:randomly -n 0 <the nine evidence, transcription and envelope suites>
    117 passed in 45.46s

Mutation proof for the retirement, with the MIME-label admission restored at
runtime from a harness outside the repository, so no tracked file was edited:

    2 failed, 2 passed, 6 deselected in 2.03s

Both new assertions red, one in each disagreement direction: the opaque-label
case refused where it must admit, and the unreadable-bytes case reported
DID NOT RAISE where it must refuse. The two parametrized shape assertions stayed
green under the same mutation, correctly - they read the probe, which the
mutation does not touch, so they are not the discriminating gates and are not
claimed as such.

## Notes

The gate is structural rather than behavioural because the failure it screens
for is silent: a caller re-deriving the routing from media_kind still produces
correct output for the two easy cases and mis-routes only the structured ones,
which reads as a slightly worse extraction rather than as a bug.

Its own first version carried the same blindness, matching only the attribute
spelling and missing the bare-parameter form. The bounding control failed and
surfaced it, which is what that control exists to do.

The structural gate could not have caught the residue the second pass removed.
It bans COMPARISONS against the two-member kind, and the surviving derivation
made none - it produced a value nothing compared. A gate written against the
branch shape is silent about a field that is merely populated, which is why the
first pass could close honestly against its own gate while the scope file it
named still held the derivation the step title said to retire.

The operator-facing `media_kind` on the evidence payload is NOT this derivation
and was deliberately left alone. It reads from the persisted record, which is
stamped at write time from the source file's EXTENSION and folded into the
content-addressed evidence id. It is storage-side - the carve-out this step's
own gate already declares deliberate - so changing it would be a persisted-record
and identity-derivation change rather than a read-path one, and belongs to its
own decision.
