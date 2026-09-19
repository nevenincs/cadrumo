---
tags:
  - '#audit'
  - '#aeat-design-relayout-boundary'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:df0053b2736ecdc46c6155c871684cd6d943c96b5b10d18e06614b8370a1cfb5'
related:
  - "[[2026-08-08-aeat-design-relayout-boundary-plan]]"
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
  - "[[2026-08-07-aeat-design-relayout-boundary-sub-year-epoch-adr]]"
  - "[[2026-08-09-aeat-design-relayout-boundary-modelo-200-fragment-tree-provenance-research]]"
---

# `aeat-design-relayout-boundary` audit: `Modelo 200 filing-capability gap: ownership, decomposition and verification-method reconciliation`

## Scope

Investigated whether Modelo 200's absent fixed-width export layout (currently
on the registry-wide "declares a completeness manifest but no export layout"
failing list) could be honestly restored from its pre-deletion git history,
following the same discipline already applied to Modelo 390: recover from the
commit that deleted it, verify every field against the modelo's own bundled
AEAT designs, and report before authoring anything. Read-only assessment.
Nothing was written under `modelos/200/**`.

## Findings

### modelo-200-has-an-existing-owner | critical | The capability gap is not orphaned; a different campaign already owns it with a conflicting approach

The export-fragment-generator-authority campaign's plan already carries this
modelo in its own rows: "Bootstrap explicit Modelo 200 semantic maps, generate
and re-key its held revisions from provenance, then delete the superseded
manual fragment tree." The owning approach is GENERATE from the official
binary design and DELETE the historical hand-transcribed tree -- the opposite
of restoring that tree from git history. The rows are unstarted, serialized
deep behind the Modelo 303 chain in the plan's own release-order line. A
restoration effort landing before or alongside those rows would directly
conflict with the owning campaign's stated plan.

### modelo-200-decomposition-not-settled | high | The closed period-selector ruling does not settle record decomposition, and 17 of 75 shared design pages differ between 2024 and 2025

The closed Step ruling that the single revision `2024-y-siguientes` correctly
names its coverage (grounded in the governing Orden's article 1, re-keying
cost outweighing any narrowing) is a ruling about the period-selector and
naming axis only; its text does not address record layout. Measured directly
against the bundled 2025 and 2024 designs (77 pages vs 75, 2025 adding two new
pages and removing none): of the 75 pages both years share, 58 are
byte-identical in offset/length sequence and 17 differ in row count and
offsets. A layout grounded only against the 2025 design -- which is what both
the deleted historical tree and every live Modelo 200 casilla currently
declare via `source_refs` -- would misplace fields on those 17 pages for a
real 2024 filing: the exact defect class this whole effort exists to catch.
This finding is not reconciled by the closed naming ruling and needs the
owning campaign's decision on whether it is answerable within one revision (a
design-epoch-scoped layout) or requires the revision to narrow.

### modelo-200-old-tree-provenance | medium | The deleted 149-fragment tree is hand-transcribed and internally self-consistent; its fidelity to the design was unmeasured until this pass

Recovered from the pre-deletion commit. The export directory was named
`export/`, not `export_layouts/` -- confirming the naming-difference trap
already responsible for two false "never existed" conclusions elsewhere
today. 149 files, 78 logical records (envelope, a DID page, and page_000
through page_054 with lettered sub-pages), 6,537 fields, of which 5,300 carry
a `casilla_id` referencing 3,248 of the revision's 3,250 declared casillas.
Every field bulk-stamps an identical `source_refs` constant naming the 2025
design, with no per-field provenance beyond that. Matches the already-recorded
provenance finding for this tree: hand-transcribed from the AEAT workbook,
with no parsing tool in existence at authoring time, so internal self-
consistency (every referenced casilla resolves) was never evidence of
external fidelity to the design's own slot numbering.

### modelo-200-verification-method-reconciled | high | A page-scoped, offset-verified cross-check resolves 97.1% of casilla-linked fields against the 2025 design; this is not the previously-retracted index-keyed technique

A prior closed measurement paired the tree's fields against the design by box
number alone, found only 36.7% (2,402 of 6,537) unambiguous, ruled both
generation and re-coordination against this tree "measured-blocked", and
attributed the ambiguity to needing position-based disambiguation, naming that
as "the index-keyed pairing the sub-year decision record already retracted."

Traced that retraction to its source ADR before writing this finding, per
instruction. The retracted technique compares two DIFFERENT designs' field
sequences against each other by ordinal position, and fails because it
"compares unrelated fields the moment either side inserts" -- an alignment
failure specific to comparing two documents positionally against one another,
the same class of defect as a naive line-by-line text diff across an
insertion.

The cross-check run for this audit is a different mechanism, not a retry of
the retracted one. For each of the 5,300 casilla-linked fields it looks up the
SAME box number on the SAME page the recovered field already declares (the
page is read from the field's own record id, never inferred or counted), then
checks whether the recovered field's own declared offset and length match one
of the design's real rows for that box on that page. This never assumes
ordinal alignment between two sequences -- it validates one already-stated
fact (the tree's own declared offset) against one ground truth (the design's
own table), keyed on (page, box number) rather than box number alone. This is
an extension of the box-number key already established elsewhere as the
reliable instrument for this class of comparison, not the rejected ordinal
instrument; the retraction does not apply to it.

Result: 5,145 of 5,300 (97.1%) exact page+offset+length matches against the
2025 design. 17 fields resolve to a box number that exists in the 2025 design
but not on the page the tree claims. 138 fields carry a box number absent from
BOTH the 2024 and 2025 bundled designs entirely. Zero fields matched the wrong
position within a correctly-identified page -- every field either matched
exactly or fell cleanly into one of the two failure buckets above, so no tie
was broken by assumption. This reconciliation concludes the prior measurement
described a real problem (a hand-transcribed tree has no structural reason to
align with the design's own slot sequence) but its 36.7% figure undercounted
verifiable fidelity, because it used neither page context nor the tree's own
declared offsets as a key, and both are available without positional
inference.

### modelo-200-bounded-worklist | low | 138 casilla-linked fields cite a box number found in neither bundled design year

Distinct from the 17 wrong-page fields above. These 138 box numbers were
searched across every row of both the 2024 and 2025 bundled design extracts
and found in neither, concentrated on two of the tree's records in the sample
drawn. Not cross-checked against the pre-2024 bundled designs (2010-2023),
which are outside the current revision's claimed coverage and were not read
for this pass. This is a finite, named population, not a sampling estimate.

## Recommendations

### Do not restore the historical `export/` tree, and do not author a fresh layout, under this row

Modelo 200 is owned by the export-fragment-generator-authority campaign's
rows for it. Its approach (generate from binary, delete the manual tree) is
incompatible with restoring or hand-deriving a layout now. No further work
against Modelo 200's export-layout fragments should proceed outside that
campaign's rows without an explicit reconciling decision.

### The record-decomposition finding needs a ruling from the owning campaign, not from this audit

Whether the 17-page 2024/2025 divergence is answered by a design-epoch-scoped
layout within the single `2024-y-siguientes` revision, or requires the
revision itself to narrow, is an architecturally significant call belonging
to whichever campaign authors the generated layout or to a follow-on ADR
amending the sub-year epoch decision's scope to cover Modelo 200. This audit
states the measurement; it does not decide the mechanism.

### If the historical tree is ever revisited as a cross-check input, use page-plus-offset keying, not box-number-alone or ordinal-index keying

The reconciliation above is worth carrying into any future Modelo 200
generation effort as a validation input: 5,145 of the tree's fields are
independently confirmed against the 2025 design's own table, which is real
corroborating signal even though the tree's provenance finding means it can
never itself be certified as AEAT-grounded. The 138-field worklist should be
resolved by hand before the tree is used even as a soft cross-check.
