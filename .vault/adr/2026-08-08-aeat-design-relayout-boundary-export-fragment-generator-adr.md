---
tags:
  - "#adr"
  - "#aeat-design-relayout-boundary"
date: '2026-08-08'
related:
  - "[[2026-08-07-aeat-design-relayout-boundary-adr]]"
  - "[[2026-08-08-aeat-design-relayout-boundary-plan]]"
  - "[[2026-08-07-aeat-design-relayout-boundary-research]]"
superseded_by: '2026-08-10-aeat-export-fragment-generator-authority-adr'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:b5d5f0bed44800627d3352180d55c2e1ff38f3dd21863c2779949129e7d43699'
---
# `aeat-design-relayout-boundary` adr: `the export fragment tree is generated from the bundled diseno, never transcribed` | (**status:** `superseded`)

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

**AMENDED: the diseno supplies COORDINATES ONLY, and this record's first pass
overstated what a generator could derive.** A bundled design gives, per field, its
sheet, row, ordinal, offset, length, type code and description. A loadable fragment
requires more than that, and the remainder is registry-side knowledge the design
does not carry: which registry casilla occupies a slot (`casilla_id`), the slot's
semantic role (`kind`), the non-casilla variants (`header_key`, `draft_attribute`),
and per-field `legal_refs`. Measured on a single Modelo 200 fragment, field blocks
take **four different key sets** — 31 carrying `casilla_id`, 23 without one, 2
carrying `header_key`, 1 carrying `draft_attribute`. Which set a field takes is a
semantic judgement, not a coordinate.

Scale, because it decides whether hand-authoring is even arguable: Modelo 200's
existing tree is 149 files, 5.0 MB and 148 record blocks for ONE revision. Modelo
303 needs five such trees and Modelo 390 four.

This record decides the mechanism. It makes no registry edit and generates
nothing itself.

## Considerations

- The parse half already exists and is trusted. `extract_record_design_workbook`,
  `extract_record_design_xls_workbook` and `extract_record_design_pdf` return
  typed `RecordDesignSheet` objects. The span gate has depended on them all
  campaign, and every boundary measurement in this feature comes through them.
  What is missing is the emit half.
- A generated fragment tree is upstream of every fichero this application
  produces. A wrong offset is not a wrong number in a box: measured on Modelo
  390, an export on the older side of a boundary succeeded and wrote the total
  cuota at byte 1628 against a record declared to end at 1526. So the mechanism is
  a filing-correctness authority, not a developer convenience.
- **The casilla-to-official-box mapping a full generator would need is the input
  this campaign has already documented as unreliable.** The span gate is keyed on
  design-to-design agreement SPECIFICALLY because that mapping "barely exists for
  some modelos" — its own docstring records that a number-keyed check reports
  hundreds of false absences on Modelo 390, whose casillas are semantic ids
  against a box-numbered design. Building a mechanism whose required input is the
  thing already known to be untrustworthy is the wrong order.
- The corpus is authoritative but the PARSERS have measured blind spots, and any
  mechanism inherits every one. The bracketed box marker was capped at four digits
  while Modelo 200 numbers its boxes with five, so the box signals read 23 of
  3,440 boxes there; a flattened PDF parse collapses a document to one synthetic
  sheet, so `(sheet, offset, length)` stops identifying a slot; and the same file
  bundled as `.xls` and `.xlsx` is byte-different while being one design.
- **AMENDED: the fixture is NOT hand-verified, and this record twice said it was.**
  Modelo 200's 149-file tree is **of unrecorded provenance, believed correct because
  nothing has contradicted it.** Traced through history: its export layout appears in
  `cdcd5b11d5` (2026-05-06), a **171-file, 158,013-insertion** commit whose subject is
  "Implement secure persistence and registry slices" and whose **body is empty**, with
  the 6,610 lines of layout arriving alongside secure persistence, locale files and
  unrelated tests. The four vault index files it touches belong to OTHER features. **No
  ADR, plan or exec record accompanies the layout.** Every commit after it is
  restructuring rather than authoring: `200.toml` moved into a revision directory, a
  132,896-line monolith fragmented into 149 files, oversized fragments split, and a
  package-root rename.
- **No joining tool ever existed, at any point in this repository's history.** Searched
  all history for a `dev/` module named for design, diseno, export layout or fichero:
  one file, `sync_aeat_record_design_corpus.py`, which DOWNLOADS the design corpus and
  emits zero registry TOML. So nothing was built and later removed — the step from
  design to fragment has never been mechanised or recorded.
- **Therefore the authorising record's "parsed from the bundled corpus, never
  hand-transcribed" requirement was never met for this tree.** It is the artefact the
  split is meant to divide and the fixture a reproduction gate would compare against,
  and its derivation is unestablished.
- **Byte-for-byte reproduction is the wrong proof target, and this record's first
  pass named it.** There is no TOML serializer anywhere in the tree: registry TOML
  is hand-rendered text, and the existing fragments carry human partitioning
  choices — `0002-...part-001` and `part-002` split at 815 and 819 lines. A
  byte-equality gate would therefore test formatting and a human's split decision
  rather than correctness, and would fail for reasons that do not matter while
  passing nothing extra that does.
- A silent partial output is the failure mode this corpus actually produces. A
  parser that cannot read a design returns the same answer as a design with no
  content, and this campaign has three instances of exactly that reading as
  success: a coverage report saying "0 casillas, 0 gap" for 36 of 38 revisions, a
  box marker matching nothing on a modelo, and a description pass over a
  mis-derived population asserting 1,462 changes.

## Considered options

- **Re-coordinate an existing tree against a different design (CHOSEN).** Take
  ONLY offsets and lengths from the bundled diseno, and preserve `casilla_id`,
  `kind`, the non-casilla variants, `legal_refs` and record structure from the tree
  that already exists and is believed correct. Pro: derives from the corpus exactly
  what the corpus can supply and nothing it cannot; needs no casilla-to-box mapping
  to be authored; the reviewer's diff is artefact against corpus. Con: the MATCHING
  step — pairing a tree field to its design slot — needs a key, and where the box
  number is absent that key is not guaranteed unique.
- **Generate the whole tree from the diseno.** Rejected as primary. It requires a
  casilla-to-box mapping authored and verified per modelo, which is the input the
  span gate exists to avoid depending on. It remains the shape to revisit if a
  mapping is ever established independently.
- **Derive each new tree by transforming its NEIGHBOUR wholesale.** Rejected.
  Across the Modelo 200 boundary 1,140 of 3,194 shared boxes moved, 246 were added
  and 145 removed, so the transform is nearly a rewrite while presenting as an
  adjustment. It also makes one revision's tree the SOURCE of another's, so a
  reviewer diffs two generated artefacts rather than an artefact against the
  corpus. Re-coordination is distinguishable precisely here: its coordinates come
  from the design, not from a sibling tree.
- **Hand-author each tree from the published design.** Rejected, and forbidden by
  the authorising record. 148 record blocks per revision across nine revisions is
  not reviewable, and a transcription error is invisible precisely where it
  matters.
- **Emit once and maintain by hand thereafter.** Rejected. It makes the generated
  artefact authored, so a corpus correction requires a manual sweep and the output
  stops being reproducible.

## Constraints

- The bundled diseno is the sole source of COORDINATES. The mechanism MUST NOT
  take an offset or a length from another tree, a `.extracted.md` derivative, or
  any transcription.
- **The casilla mapping is an explicit, per-modelo AUTHORED input with its own
  verification, never something the mechanism derives.** Under re-coordination it
  is supplied implicitly by the existing tree; under any future full generation it
  must be authored and verified before use.
- **The matching step MUST refuse on ambiguity and never guess.** Pairing a tree
  field to its design slot must be unambiguous per field. Where a bracketed box
  number is present, matching uses the registry's CANONICAL marker, never a local
  copy. Where it is absent, any secondary key must be proven to identify exactly
  one slot. **If any field cannot be matched unambiguously, the whole tree is
  refused and the field is named** — a partial re-coordination is the same failure
  as a partial emission: output that passes review and mis-files.
- The match rate MUST be measured and reported before any tree is emitted. If a
  meaningful share of fields cannot be matched, re-coordination carries the same
  defect as full generation and the mechanism is reconsidered rather than built on.
- It MUST refuse loudly rather than emit a partial tree, naming the file and the
  reason, for an unparseable design, a sheet with no declared total, or a field
  with no coordinates.
- It MUST consume the registry's canonical bracketed-box marker rather than
  declaring its own. Three test modules independently re-declared that pattern at
  four digits while production used five; a fourth copy inside this mechanism would
  reproduce that defect in SHIPPED REGISTRY DATA rather than in a gate.
- **Proof is LOADER-SEMANTIC EQUIVALENCE, not byte equality** — the loader is what
  consumes fragments, so the loader's view is the contract while formatting and file
  partitioning are not.
- **AMENDED: and that proof is bounded. Reproducing the existing tree demonstrates
  AGREEMENT WITH AN UNVERIFIED BASELINE, not correctness against AEAT.** The fixture's
  derivation is unrecorded, so a gate built on it detects divergence from shipped
  behaviour — a real and useful property — and **cannot discharge a correctness
  obligation.** This record's earlier passes implied it could. An ADR that overstates
  its own proof is a shape this campaign has corrected twice, and this is the third.
- Emitted fragments are REGENERABLE ARTEFACTS, not authored ones. A correction to
  a design, a parser or the mechanism is fixed at the source and re-run; nobody
  hand-edits emitted fragments. Output is deterministic and carries its provenance.
- Every emitted fragment declares `source_refs` naming the specific
  `aeat-dr-<modelo>-<year>` design entry its coordinates came from.
- The mechanism lives under `dev/`, not in the shipped package.

## Implementation

Add a re-coordination tool under `dev/registry/` that takes a modelo, a source
revision's existing fragment tree, and a target bundled design. It parses the
design through the shipped `_record_design` extractors, matches each tree field to
exactly one design slot, and emits a fragment tree identical to the source in
`casilla_id`, `kind`, refs and record structure while carrying the target design's
offsets and lengths, keyed on the target revision id, with `source_refs` naming the
target design entry.

Build the MATCH MEASUREMENT first and report it before emitting anything. Match
Modelo 200's existing tree against the design it already declares and report, per
field, whether it pairs to exactly one slot. That number decides whether the
mechanism is viable at all.

Then gate by loader-semantic equivalence: re-coordinate Modelo 200's tree against
its OWN design and require the loaded export layout to equal the layout loaded from
the untouched tree. Re-coordinating a tree against the design it already encodes
must be an identity operation, so any divergence is a defect in the mechanism or in
the matching key rather than a real change — which makes it the sharpest available
control, and it needs no second artefact to compare against.

Where a divergence is adjudicated in the existing tree's favour, that is a parser
or design-reading gap and it is recorded with its reason. The existing tree is of
unrecorded provenance and may itself be wrong, so it is explicitly not an oracle: a
divergence resolved either way is a finding, never a tolerance. That at least one
shipped layout IS wrong is established — Modelo 390 exported a total cuota at byte
1628 against a record its own design declares ending at 1526.

## Rationale

Re-coordination wins on the same principle that decided every other question this
campaign: derive from a source only what that source can actually supply. The
diseno supplies coordinates and cannot supply the casilla mapping. Full generation
needs that mapping authored per modelo, and the span gate exists precisely because
it cannot be trusted — so full generation's required input is the thing already
known to be unreliable, while re-coordination needs no mapping to be authored at
all because it preserves one already believed correct.

The identity-operation gate is the strongest control available against the shipped
tree, and that is a weaker claim than it first appears. Re-coordinating a tree
against its own design must change nothing, so the expected output is known exactly
and needs no second artefact. But the baseline it compares against has no
established derivation, so the gate bounds regression rather than establishing
correctness.

Refusing the whole tree on a single unmatched field follows the shape corrected
repeatedly today: a mechanism returning a confident answer where the honest output
is a refusal is the expensive failure. A partial tree is plausible, reviewable and
wrong.

## Consequences

- Every remaining split Wave depends on this mechanism, so it is sequenced before
  Modelo 390 and Modelo 303. Modelo 200's 2024 revision is held behind it and that
  filing year refuses in the meantime, which is the authorising record's stated
  posture for a year that cannot be served correctly.
- **This record's promise of one authority instead of nine transcriptions holds
  for COORDINATES ONLY, and not for the casilla mapping.** The mapping is an
  authored input with no generator behind it: under re-coordination it is inherited
  from an existing tree whose own authoring was manual and is believed rather than
  proved. So the mapping remains a hand-maintained authority, and this record does
  not close that gap. Stating it because an ADR that overstates its own reach is a
  shape this campaign has corrected twice.
- The matching key is the mechanism's load-bearing weakness. Where a design slot
  carries no bracketed box number the pairing depends on a secondary key, and that
  is the most likely place for a silent error. The refuse-on-ambiguity constraint
  is what converts that risk into a stoppage rather than a mis-file.
- The mechanism inherits every parser blind spot, and closing one later changes
  emitted registry data rather than only a gate's verdict.
- A design correction becomes a re-run. A reviewer therefore reads a diff between
  generated artefacts and must consult the design to judge it; the provenance
  `source_refs` exists to make that possible.
- Re-coordinating Modelo 200's tree may surface defects in that tree rather than in
  the mechanism. Those are findings about shipped registry data and are recorded as
  such, not accommodated by loosening the gate.
- Nothing here re-coordinates anything. A reader who takes this record as the fix
  will believe the split is authorable when it is not.
