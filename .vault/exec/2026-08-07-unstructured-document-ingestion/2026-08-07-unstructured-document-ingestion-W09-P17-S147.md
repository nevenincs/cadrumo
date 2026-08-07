---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:d9d725293b58452af51cd7e63707898f2ca264c4d0babed7bf39bfb169a9424a'
step_id: 'S147'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
## Scope

- `src/cadrumo/application/ledger`

## Description

- Land the gate first, red, ahead of the behaviour it guards.
- Factor the anchor check onto plain source text so both reading lanes share one
  implementation.
- Add a structured entry point beside the sanctioned anchored one, stamping the
  origin the taxonomy already reserves.
- Build one envelope per value the record actually stated, in the structured
  projection.

## Outcome

Provenance is required to travel every domain boundary to the operator-facing
surface. The structured projection built none for any field — not the tax
identifier, not the regime legend, not the postal codes — so a value read
EXACTLY from a machine-readable record, with no model anywhere near it and prompt
injection categorically impossible, arrived at the operator with no origin at
all, while a heuristic recovery from a PDF text layer arrived with a full
envelope. The most defensible values in the system were getting the least
apparatus.

### The origin member already existed; nothing had to be invented

The campaign note said no production site constructs an exact-structured field
origin. That is true, and it describes a missing *producer* rather than a missing
member: `EXACT_STRUCTURED` is already declared in the core taxonomy, documented
as "read from the document's own machine-readable record", and referenced by the
grounded-reading module's accepted-origin set. So the taxonomy needed no new
member and no owner had to be consulted — the gap was that nothing ever stamped
it.

### Why a sibling entry point rather than the existing constructor

The sanctioned constructor for an anchor-checked envelope takes a document
transcription. Running the substitutability check on it: a transcription's
contract requires a page count of at least one ("a transcription of no pages is a
failed read"), a transcriber identity naming which reader produced the text at
which revision, and reading-order text with printed forms preserved. A
machine-readable record has none of those — no pages, no reading order, and no
transcriber, because a parser is not one. Satisfying the signature would have
meant synthesising a page count and a reader that never existed.

So the constraint shape does not cover this case, exactly as it did not for an
earlier candidate precedent on this campaign. What DOES transfer is the module's
purpose: a path that constructs an envelope itself and hand-sets the anchored
outcome is asserting the check rather than running it. The answer is therefore a
sibling entry point in the same module, under the same authority, with the
two-part check factored into one shared implementation both lanes call. The
lanes differ only in which text is authoritative — a transcription for a rendered
page, the record's own bytes for a machine-readable document — so that is the
parameter, and there is one checker rather than two that can drift.

### The anchor is the record's verbatim text; the element path is not evidence

Decided rather than defaulted. The anchor field means the form the value was read
from, and a downstream consumer reads it as evidence about what the document
states. An element path is a location: true, useful for navigation, and not
evidence. Putting a schema path there would let a consumer treat it as the form a
human would see on the page. So the anchor carries the record's own verbatim text
and the element path rides in the note, where an operator can still use it to
find the value and nothing can mistake it for a printed form. A gate asserts the
anchor is the value and carries no path separator.

The paths themselves are named per format only where they have been confirmed
against a real specimen of that format; every other field falls back to naming
the shape and the field, which is always true. A path stated from memory would be
a navigation instruction pointing at an element the document may not have, and a
wrong location is worse than none because it reads as authoritative.

### The check is real, and it already refuses a value on the bundled corpus

The strongest evidence that this is not ceremony came out of the corpus rather
than from a manufactured case. Facturae states a natural person's name across
three elements, and the reader joins them into the single display name the
document means — so the assembled string appears nowhere in the record, and the
check declines to vouch for it. The value still reaches the operator; only the
claim that it was read verbatim is withheld.

That is the mechanism working: the joined name is the right value to carry and
the wrong thing to call verbatim. It also means the check is falsifiable on real
input, which a check satisfied by every field of the corpus would not be.

What the check cannot do is prove the reader chose the RIGHT element — an anchor
found somewhere in the record does not prove it was found in the right place.
That is the same limit the transcription lane already has, and it is documented
on the entry point rather than left for a reader to discover.

## Verification

The gate, five cases through the real encrypted evidence path:

    uv run --no-sync pytest src/cadrumo/application/ledger/tests/test_structured_path_provenance.py -n0 -m "unit" -p no:randomly
    5 passed in 2.30s

Regression across the ledger application suite and the e-invoice adapter:

    uv run --no-sync pytest src/cadrumo/application/ledger/tests src/cadrumo/adapters/inbound/einvoice/tests -n0 -m "unit or integration" -p no:randomly
    975 passed, 15 warnings in 245.27s (0:04:05)

Lint, format and type checks clean under `ruff check`, `ruff format` and
`ty check`.

### Mutation proofs

Both installed from a plugin module outside the repository at plugin scope, each
asserting the replacement is not the original and printing on install. No tracked
file was edited.

Restoring the original defect, a projection that builds no envelopes:

    MUTATION INSTALLED: structured projection builds no provenance
    5 failed in 2.53s

Every case reddens, which is the expected shape when the whole capability is
removed.

Asserting the anchored outcome instead of running the check — the failure the
grounding module exists to make unnecessary:

    MUTATION INSTALLED: ANCHORED asserted without running the check
    2 failed, 3 passed in 3.13s

This is the proof that matters. A path that hand-sets the outcome produces the
same payload SHAPE as one that ran the check, so a gate reading only the payload
cannot tell them apart. Exactly the two cases that look past the shape reddened;
the three that assert origin, presence and anchor form stayed green, correctly,
because the mutation does not change any of them.

## Notes

**Element paths are populated only where confirmed against a real specimen.**
Today that is the two postal-code fields across all three formats, verified in
the preceding Step. Every other field's note names the shape and the field
instead. Completing the table is worth doing when a specimen of each format is
available to check against, and is deliberately not done from memory.

**The grounding import is function-local**, because the anchor module reaches
back into the draft module for the envelope types. That is the same cycle break
the semantic path's grounding import already uses, and it is commented to be read
exactly as if it were at module scope.

**The production half reached the tree under another author's commit**, the sixth
such sweep observed on this campaign. The landed content is byte-identical to the
final version, verified by an empty diff afterwards. The gate half was committed
deliberately ahead of the behaviour and was not swept, so the ordering rule held
again even though the second commit was not the author's.

**The shared index was found poisoned a third time**, carrying a single tracked
test file staged as a pure deletion of 157 lines while the file exists on disk
and is committed. It was not touched, and the gate commit went in cleanly beside
it — a pathspec commit cannot carry foreign staged entries, which is what makes
the discipline rather than the timing the thing that keeps these commits clean.
