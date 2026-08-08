---
tags:
  - '#adr'
  - '#aeat-design-relayout-boundary'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:9bd0140d7e7036b9205fdeeb4e3a7f4def95f7497c15feb90c8df273c1e84807'
related:
  - '[[2026-08-07-aeat-design-relayout-boundary-adr]]'
  - '[[2026-08-08-aeat-design-relayout-boundary-plan]]'
  - '[[2026-08-07-aeat-design-relayout-boundary-research]]'
---
# `aeat-design-relayout-boundary` adr: `the export fragment tree is generated from the bundled diseno, never transcribed` | (**status:** `accepted`)

## Problem Statement

Splitting a registry revision at an AEAT design re-layout requires one export
layout fragment tree per resulting revision, each encoding its own design's byte
offsets. `2026-08-07-aeat-design-relayout-boundary-adr` requires those fragments
be "parsed from the bundled corpus, never hand-transcribed" and authorises the
split; the implementing plan repeats the requirement per revision.

**No tooling exists to produce one.** Searched semantically and by grep across
`dev/` and `src/`: the registry loader reads fragments, `_export.py` holds their
schema, `_record_design.py` parses a bundled diseno into typed sheets and fields,
and `dev/registry/newmodelo/` scaffolds a new modelo while listing "register the
export layout(s)" as a MANUAL checklist item. Nothing joins the parser to the
fragment schema.

So the authorised split is unauthorable. The gap was found by the campaign's
Modelo 200 pilot, whose principal finding is not the split it was meant to prove
but that the authoring pattern was never specified: the unstated judgement is how
a fragment tree comes into existence at all. It blocks all three modelo Waves.

Scale, because it decides whether hand-authoring is even arguable: Modelo 200's
existing tree is 149 files, 5.0 MB and 148 record blocks for ONE revision. Modelo
303 needs five such trees and Modelo 390 four.

This record decides the mechanism. It makes no registry edit and generates
nothing itself.

## Considerations

- The parse half already exists and is trusted. `extract_record_design_workbook`,
  `extract_record_design_xls_workbook` and `extract_record_design_pdf` return
  typed `RecordDesignSheet` objects carrying, per field, its sheet, row, ordinal,
  offset, length, type code and description. The span gate has depended on them
  all campaign, and every boundary measurement in this feature comes through
  them. What is missing is the emit half.
- A generated fragment tree is upstream of every fichero this application
  produces. A wrong offset is not a wrong number in a box: measured on Modelo
  390, an export on the older side of a boundary succeeded and wrote the total
  cuota at byte 1628 against a record declared to end at 1526. So the generator
  is a filing-correctness authority, not a developer convenience, which is why it
  gets a decision record rather than a helper module.
- The corpus is authoritative but the PARSERS have measured blind spots, and the
  generator inherits every one. The bracketed box marker was capped at four
  digits while Modelo 200 numbers its boxes with five, so the box signals read 23
  of 3,440 boxes there; a flattened PDF parse collapses a document to one
  synthetic sheet, so `(sheet, offset, length)` stops identifying a slot; and the
  same file bundled as `.xls` and `.xlsx` is byte-different while being one
  design. Each was found this campaign, and each would have produced a plausible
  fragment tree.
- Reproducing an existing tree is available as a control and is the only one that
  does not require trusting the thing under test. Modelo 200's 149-file tree was
  authored before this campaign and is believed correct; its manifest declares
  `source_refs = ["aeat-dr-200-2025"]` and it carries 78 distinct record ids
  consistent with the 2025 design's 77-record decomposition. A generator run
  against that same design must reproduce that tree.
- A silent partial parse is the failure mode this corpus actually produces. A
  parser that cannot read a design returns the same answer as a design with no
  content, and the campaign has three instances of exactly that reading as
  success: a coverage report saying "0 casillas, 0 gap" for 36 of 38 revisions, a
  box marker matching nothing on a modelo, and a description pass over a
  mis-derived population asserting 1,462 changes.
- Fragment trees are already fragmented by convention: a revision's export lives
  in numbered per-page files, some split into `part-00N`. That shape is the
  loader's, not an author's preference, so a generator must emit it rather than
  one large file.

## Considered options

- **Generate the fragment tree from the bundled diseno, and gate the generator by
  reproducing an existing hand-verified tree (chosen).** Pro: one authority for
  every offset, derived from the corpus the gate already treats as authoritative;
  a design correction becomes a re-run rather than a manual sweep; the proof
  obligation is available without trusting the generator. Con: new tooling with a
  filing-correctness burden, and it inherits every parser blind spot.
- **Derive each new tree by transforming its neighbour.** Rejected. Across the
  Modelo 200 boundary 1,140 of 3,194 shared boxes moved, 246 were added and 145
  removed, so the transform is nearly a rewrite while presenting as an
  adjustment. It also makes one revision's tree the SOURCE of another's, so an
  error in the first silently becomes an error in both, and the diff a reviewer
  reads is between two generated artefacts rather than between an artefact and
  the corpus. It carries a generator's correctness burden with less visibility.
- **Hand-author each tree from the published design.** Rejected, and forbidden by
  the authorising record. 148 record blocks per revision across nine revisions is
  not reviewable, and a transcription error is invisible precisely where it
  matters — a plausible offset in a valid-looking file.
- **Emit the tree once and maintain it by hand thereafter.** Rejected. It makes
  the generated artefact authored, so a corpus correction requires a manual sweep
  and the generator's output stops being reproducible. The regenerable-artefact
  ruling below exists to prevent this drift.

## Constraints

- The bundled diseno is the SOLE source. The generator MUST NOT read another
  revision's fragments, a `.extracted.md` derivative, or any transcription. It
  reads the design SOURCE through the shipped parsers.
- It MUST refuse loudly rather than emit a partial tree. A design that parses to
  nothing, a sheet with no declared total, a field with no offset or length, or a
  modelo whose bracketed box numbers the marker cannot read are all refusals
  naming the file and the reason — never a tree with the unreadable part omitted.
  A partial tree is the one output that passes review and mis-files.
- It MUST consume the registry's canonical bracketed-box marker rather than
  declaring its own. Three test modules independently re-declared that pattern at
  four digits while production used five, and the generator declaring a fourth
  copy would reproduce that defect in shipped registry data rather than in a gate.
- Generated fragments are REGENERABLE ARTEFACTS, not authored ones. Any
  correction to a design, a parser or the generator is fixed at the source and
  re-run; nobody hand-edits emitted fragments. The generator is therefore
  deterministic — same design in, byte-identical tree out — and its output
  carries its provenance.
- Every emitted fragment declares `source_refs` naming the specific
  `aeat-dr-<modelo>-<year>` design entry it was generated from, so a later reader
  can re-derive the tree from the record rather than trusting it.
- The generator lives under `dev/`, not in the shipped package. It is authoring
  tooling and runs from a repository checkout; the wheel carries the generated
  registry data, never the generator.

## Implementation

Add a generator under `dev/registry/` that takes a modelo, a revision id and a
bundled design, parses the design through the shipped `_record_design` extractors,
and emits the numbered per-page fragment files the loader expects, keyed on the
target revision id, with `source_refs` naming the design entry.

Gate it by REPRODUCTION before it authors anything. Run it against the design
Modelo 200's existing tree declares — `aeat-dr-200-2025` — and require the output
to match that tree. A generator that cannot reproduce a tree already believed
correct cannot be trusted to author one nobody can check, so this is a gate rather
than a smoke test, and it is the first thing built.

Where the reproduction diverges, the divergence is adjudicated against the design
rather than assumed to be the generator's fault: the existing tree is
hand-authored and may itself be wrong. Any divergence resolved in the tree's
favour is recorded with the reason, so the fixture's authority is explicit rather
than inherited.

Refusals are named and total. An unparseable design, an unreadable sheet, a field
without coordinates, or a box-number population the canonical marker cannot read
each raise, naming the file, and no fragment is written for that design.

## Rationale

The knockout against every alternative is visibility. Hand-authoring and
neighbour-transforming both produce a reviewable-looking artefact whose errors are
plausible offsets in valid files, and this campaign has repeatedly shown that a
mechanism returning a confident answer where the honest output is a refusal is the
expensive failure — the four-digit marker reading 0.4% of a modelo while reporting
nothing amiss, a coverage report reading "0 gap" for 36 of 38 revisions, two
instruments agreeing because they shared a blind spot. A generated tree derived
from the corpus, with the corpus as its only input, is the one shape whose
correctness a reader can re-derive.

The reproduction gate is the load-bearing half of the decision rather than a
testing detail. It is the only available control that does not require trusting
the generator, because the fixture predates it and was authored by a different
method. Without it, the generator's first output is also its first unverifiable
one, on nine revisions nobody can check by hand.

Declaring fragments regenerable rather than authored is what keeps the corpus
authoritative over time. If a design correction requires a manual sweep, the
emitted tree becomes the real authority the moment anyone edits it, and the
generator degrades into a one-off scaffold — which is how the four hand-maintained
terminology stores this project already retired came about.

## Consequences

- Every remaining split Wave depends on this generator, so it is sequenced before
  Modelo 390 and Modelo 303 rather than alongside them. Modelo 200's 2024
  revision is held behind it and that filing year refuses in the meantime, which
  is the authorising record's stated posture for a year that cannot be served
  correctly.
- The generator inherits every parser blind spot, and closing one later changes
  emitted registry data rather than only a gate's verdict. That raises the cost of
  a parser fix and is the price of having one authority instead of nine
  transcriptions.
- A design correction becomes a re-run. That is the intended property, and it
  means a reviewer reads a diff between generated artefacts and must consult the
  design to judge it — the provenance `source_refs` exists to make that possible.
- Reproducing Modelo 200's tree may surface defects in that tree rather than in
  the generator. Those are findings about shipped registry data and are recorded
  as such, not silently accommodated by loosening the gate.
- Nothing here generates anything. A reader who takes this record as the fix will
  believe the split is authorable when it is not; the generator and its
  reproduction gate are the implementing work.
